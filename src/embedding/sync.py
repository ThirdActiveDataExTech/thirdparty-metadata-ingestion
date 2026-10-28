"""벡터 테이블 증분 동기화.

**전량 재생성하지 않는다.** 기존 scripts/embed_*.py는 매번
`DELETE FROM *_vec` 후 전부 다시 만들었다. 29,029건을 매 수집마다 다시 인코딩하는
것은 낭비이고, 수집 중 삭제된 상태가 노출되는 구간도 생긴다.

대신 **임베딩 입력 텍스트(embed_text)를 비교**해 바뀐 것만 다시 만든다.
  - vec 행이 없다           → 신규 생성
  - 저장된 embed_text가 다르다 → 원본이 바뀐 것이므로 재생성
  - 같다                    → 건너뜀

텍스트 비교는 DB에서 끝나므로 모델을 올리지 않고도 "할 일이 없음"을 알 수 있다.
"""

import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.database.db import get_conn
from src.embedding import embedder

logger = logging.getLogger(__name__)


def _text_dataset(row: Dict[str, Any]) -> str:
    """dcat_dataset: 제목 + 설명 + 키워드."""
    kws = row.get("keywords") or []
    if isinstance(kws, str):
        kws = json.loads(kws)
    kw = ", ".join(kws) if kws else ""
    parts = [row.get("title") or "", row.get("description") or ""]
    if kw:
        parts.append(f"키워드: {kw}")
    return ". ".join(p for p in parts if p)


def _text_video(row: Dict[str, Any]) -> str:
    """meta_video: 제목 + 설명 + 태그."""
    tags = row.get("tags") or []
    if isinstance(tags, str):
        tags = json.loads(tags)
    tag = ", ".join(tags) if tags else ""
    parts = [row.get("title") or "", row.get("description") or ""]
    if tag:
        parts.append(f"태그: {tag}")
    return ". ".join(p for p in parts if p)


def _text_article(row: Dict[str, Any]) -> str:
    """meta_news / meta_blog: 제목 + 요약 (+ 본문 앞 500자).

    본문 스크래핑에 실패한 항목(has_content=FALSE)은 제목·요약만 쓴다.
    max_seq_length가 128이라 500자를 넘겨도 앞부분만 반영되지만, 잘라 넘기는 편이
    토크나이저 비용을 줄인다.
    """
    parts = [row.get("title") or "", row.get("description") or ""]
    if row.get("has_content"):
        parts.append((row.get("content") or "")[:500])
    return ". ".join(p for p in parts if p)


# (원본 테이블, 벡터 테이블, 키 컬럼, 조회 컬럼, 텍스트 생성 함수)
_SPECS: Dict[str, Tuple[str, str, str, str, Callable]] = {
    "dcat_dataset": ("dcat_dataset", "dcat_dataset_vec", "dataset_id",
                     "dataset_id, title, description, keywords", _text_dataset),
    "meta_video":   ("meta_video", "meta_video_vec", "meta_id",
                     "id, title, description, tags", _text_video),
    "meta_news":    ("meta_news", "meta_news_vec", "meta_id",
                     "id, title, description, content, has_content", _text_article),
    "meta_blog":    ("meta_blog", "meta_blog_vec", "meta_id",
                     "id, title, description, content, has_content", _text_article),
}


def sync(spec_name: str, dataset_id: Optional[str] = None,
         limit: Optional[int] = None) -> Dict[str, int]:
    """벡터 테이블을 원본과 맞춘다. 반환: {'checked','embedded','skipped'}.

    dataset_id를 주면 그 데이터셋 소속만 처리한다(수집 파이프라인용).
    limit은 한 번에 인코딩할 최대 건수 — 첫 전량 생성처럼 큰 작업을 여러 번에
    나눠 돌릴 때 쓴다. 남은 건 다음 호출에서 이어 처리된다.
    """
    base, vec, key, cols, build = _SPECS[spec_name]
    conn = get_conn()
    try:
        cur = conn.cursor()
        where, params = "", []
        if dataset_id is not None:
            # dcat_dataset은 PK가, meta_*는 FK가 dataset_id라 조건식이 같다
            where = " WHERE b.dataset_id = %s"
            params.append(dataset_id)
        src_key = cols.split(",")[0].strip()
        cur.execute(
            f"SELECT {', '.join('b.' + c.strip() for c in cols.split(','))}, v.embed_text "
            f"FROM {base} b LEFT JOIN {vec} v ON v.{key} = b.{src_key}{where}",
            params,
        )
        names = [d[0] for d in cur.description]
        rows = [dict(zip(names, r)) for r in cur.fetchall()]

        todo: List[Tuple[Any, str]] = []
        skipped = 0
        for r in rows:
            text = build(r)
            if not text:
                skipped += 1
                continue
            if r.get("embed_text") == text:
                skipped += 1
                continue
            todo.append((r[src_key], text))

        checked = len(rows)
        if not todo:
            logger.info("%s 임베딩: 변경 없음 (검사 %d건)", spec_name, checked)
            return {"checked": checked, "embedded": 0, "skipped": skipped}

        pending = len(todo)
        if limit is not None and pending > limit:
            todo = todo[:limit]
        logger.info("%s 임베딩: 대상 %d건 중 %d건 처리", spec_name, pending, len(todo))

        vectors = embedder.encode([t for _, t in todo])
        for (pk, text), vec_list in zip(todo, vectors):
            cur.execute(
                f"INSERT INTO {vec} ({key}, embedding, embed_text, model_name) "
                f"VALUES (%s, %s::vector, %s, %s) "
                f"ON CONFLICT ({key}) DO UPDATE SET "
                f"  embedding = EXCLUDED.embedding, "
                f"  embed_text = EXCLUDED.embed_text, "
                f"  model_name = EXCLUDED.model_name, "
                f"  embedded_at = now()",
                (pk, str(vec_list), text, embedder.MODEL_NAME),
            )
        conn.commit()
        return {"checked": checked, "embedded": len(todo), "skipped": skipped}
    finally:
        conn.close()


def sync_for_dataset(source_type: str, dataset_id: str,
                     limit: Optional[int] = None) -> Dict[str, int]:
    """수집 파이프라인이 부르는 진입점. 데이터셋 카탈로그 + 아이템 벡터를 맞춘다.

    shopping_insight·persona_insight는 아이템이 카테고리라 본문이 없다 —
    데이터셋 단위 임베딩만 한다.
    """
    result = sync("dcat_dataset", dataset_id=dataset_id)
    item_spec = {"video": "meta_video", "news": "meta_news", "blog": "meta_blog"}.get(source_type)
    if item_spec:
        item = sync(item_spec, dataset_id=dataset_id, limit=limit)
        for k in result:
            result[k] += item[k]
    return result
