"""AI 메타데이터 생성·적재 (A2).

**실패가 파이프라인을 멈추지 않는다.** 로드맵 A2가 "실패 시 레코드 스킵 +
재처리 대상 플래그(완전 실패로 파이프라인 중단 금지)"로 정해 둔 바다.
한 영상의 텍스트가 이상해서 수백 건 생성이 통째로 날아가면 안 된다.

세 상태를 구분한다.

    ok       만들었다
    skipped  입력이 너무 짧아 만들 수 없었다 — **실패가 아니다.**
             제목 한 줄로 "요약"을 만들면 원문과 같은 말이고, 받는 쪽이
             요약이 있다고 믿게 만드는 쪽이 더 나쁘다
    failed   처리 중 오류. 사유를 적어 두고 다음 영상으로 넘어간다
"""

import logging
from typing import Any, Dict, List, Optional

from psycopg2.extras import execute_values

from src.ai_meta import extractive as E
from src.database.db import get_conn
from src.search import tokenize

logger = logging.getLogger(__name__)


def _source_text(row: Dict[str, Any], transcript: Optional[str]) -> str:
    """요약·키워드의 입력. 자막이 있으면 가장 긴 재료다.

    `src/embedding/sync.py::_text_video`와 같은 재료를 쓰되 **태그는 뺀다** —
    태그는 문장이 아니라 나열이라 추출 요약의 문장 후보가 되면 읽히지 않는다.
    """
    parts = [row.get("title") or "", row.get("description") or ""]
    if transcript:
        parts.append(transcript)
    return ". ".join(p for p in parts if p)


def generate_for_dataset(dataset_id: str, limit: Optional[int] = None,
                         dry_run: bool = False) -> Dict[str, int]:
    """한 데이터셋의 영상 전량에 AI 메타를 만든다.

    IDF 코퍼스는 **그 데이터셋의 영상들**이다. 밖까지 넓히면 "같은 채널의 다른
    영상과 구별 짓는 말"이 아니게 되어 채널 공통어가 전부 살아남는다.
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, video_id, title, description, has_transcript "
        "FROM   meta_video WHERE dataset_id = %s ORDER BY id",
        (dataset_id,),
    )
    names = [d[0] for d in cur.description]
    rows = [dict(zip(names, r)) for r in cur.fetchall()]
    if not rows:
        logger.warning("%s: 영상이 없다", dataset_id)
        return {"total": 0, "ok": 0, "skipped": 0, "failed": 0}

    # 자막은 플래그가 켜진 것만 읽는다(sync._attach_transcripts와 같은 이유)
    from src.storage import s3_client
    transcripts: Dict[int, str] = {}
    for r in rows:
        if not r.get("has_transcript"):
            continue
        doc = s3_client.read_json(
            f"raw/video/{s3_client.storage_key(dataset_id)}/{r['video_id']}.json")
        if doc and doc.get("full_text"):
            transcripts[r["id"]] = doc["full_text"]
    if transcripts:
        logger.info("자막 %d건 반영", len(transcripts))

    texts = {r["id"]: _source_text(r, transcripts.get(r["id"])) for r in rows}
    # 토큰을 두 벌 만든다 — 쓰임이 다르다.
    #   all   문장 점수용. 동사·형용사가 있어야 문장의 의미 밀도를 잰다
    #   nouns 사람이 읽는 키워드용. 어간(`짧`·`보`·`느끼`)이 보이면 읽히지 않는다
    tokens = {mid: tokenize.tokens(t) for mid, t in texts.items()}
    noun_tokens = {mid: tokenize.tokens(t, keep=tokenize.NOUNS)
                   for mid, t in texts.items()}
    idf = E.corpus_idf(list(tokens.values()))
    noun_idf = E.corpus_idf(list(noun_tokens.values()))
    method = f"extractive/tfidf/{tokenize.version()}"

    payload: List[tuple] = []
    counts = {"ok": 0, "skipped": 0, "failed": 0}
    for r in rows[:limit] if limit else rows:
        mid = r["id"]
        text = texts[mid]
        try:
            summary = E.summarize(text, idf, tokenize.tokens)
            kws = E.keywords(noun_tokens[mid], noun_idf)
            if summary is None:
                status, err = "skipped", None
            else:
                status, err = "ok", None
            counts[status] += 1
        except Exception as e:                    # noqa: BLE001
            # 한 건이 터져도 나머지는 만든다 — 사유를 남기고 넘어간다
            logger.warning("meta_id=%s 생성 실패: %s", mid, e)
            summary, kws, status, err = None, None, "failed", str(e)[:500]
            counts["failed"] += 1
        payload.append((mid, summary, kws, len(text),
                        bool(transcripts.get(mid)), method, status, err))

    if dry_run:
        logger.info("dry-run — %d행을 쓰지 않는다", len(payload))
        return {"total": len(payload), **counts}

    execute_values(
        cur,
        "INSERT INTO meta_video_ai (meta_id, ai_summary, ai_keywords, source_chars, "
        "                           has_transcript, method, status, error) VALUES %s "
        "ON CONFLICT (meta_id) DO UPDATE SET "
        "  ai_summary = EXCLUDED.ai_summary, ai_keywords = EXCLUDED.ai_keywords, "
        "  source_chars = EXCLUDED.source_chars, has_transcript = EXCLUDED.has_transcript, "
        "  method = EXCLUDED.method, status = EXCLUDED.status, error = EXCLUDED.error, "
        "  generated_at = now()",
        payload, page_size=500, fetch=False)
    conn.commit()
    logger.info("%s: 생성 %d · 건너뜀 %d · 실패 %d",
                dataset_id, counts["ok"], counts["skipped"], counts["failed"])
    return {"total": len(payload), **counts}
