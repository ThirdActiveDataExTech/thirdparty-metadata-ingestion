"""기존 청크에 키워드 채널 토큰을 채운다 (ADR-010).

`sql/migration_2026_10_30_keyword_channel.sql`은 컬럼만 만든다. 이미 적재된
청크의 `token_text`는 NULL이라 **키워드 채널이 0건을 반환한다** — 오류가 아니라
빈 결과라서 조용하다. 이 스크립트가 그걸 채운다.

재토큰화가 필요한 경우는 두 가지다.

1. 최초 백필 — `token_text IS NULL`
2. 토크나이저 교체 — `tokenizer_ver`가 현재 버전과 다름.
   ADR-010: "형태소 분석기를 교체해도 DB 스키마는 불변, 재색인만 하면 된다."
   **임베딩은 건드리지 않는다** — 토큰만 다시 만들면 된다.

실행:
    PYTHONPATH=. python scripts/backfill_tokens.py                # 전부
    PYTHONPATH=. python scripts/backfill_tokens.py --source news  # 한 종류만
    PYTHONPATH=. python scripts/backfill_tokens.py --limit 5000   # 나눠 돌릴 때
    PYTHONPATH=. python scripts/backfill_tokens.py --dry-run      # 대상 건수만

중단해도 안전하다. 배치마다 커밋하므로 다시 실행하면 남은 것부터 이어간다.
"""

import argparse
import logging
import sys
import time

from psycopg2.extras import execute_values

from src.database.db import get_conn
from src.search import tokenize

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# (벡터 테이블, 원본 식별 컬럼) — PK가 (키, chunk_index)라 둘 다 있어야 한 행을 짚는다
TABLES = {
    "video":   ("meta_video_vec",   "meta_id"),
    "news":    ("meta_news_vec",    "meta_id"),
    "blog":    ("meta_blog_vec",    "meta_id"),
    "dataset": ("dcat_dataset_vec", "dataset_id"),
}

BATCH = 2000


def backfill(source: str, limit=None, dry_run=False) -> int:
    table, key = TABLES[source]
    ver = tokenize.version()
    conn = get_conn()
    cur = conn.cursor()

    where = "token_text IS NULL OR tokenizer_ver IS DISTINCT FROM %s"
    cur.execute(f"SELECT count(*) FROM {table} WHERE {where}", (ver,))
    pending = cur.fetchone()[0]
    if dry_run or pending == 0:
        logger.info("%-16s 대상 %d건%s", table, pending, " (처리 안 함)" if dry_run else "")
        conn.close()
        return pending

    target = min(pending, limit) if limit else pending
    logger.info("%-16s 대상 %d건 중 %d건 처리", table, pending, target)

    done, t0 = 0, time.time()
    while done < target:
        size = min(BATCH, target - done)
        # 처리할 행을 집어 온다. 배치마다 다시 조회하므로 앞 배치가 커밋되면
        # 자연히 다음 묶음이 나온다 — OFFSET을 쓰면 안 된다(대상이 줄어든다)
        cur.execute(
            f"SELECT {key}, chunk_index, embed_text FROM {table} "
            f"WHERE {where} ORDER BY {key}, chunk_index LIMIT %s",
            (ver, size),
        )
        rows = cur.fetchall()
        if not rows:
            break

        payload = [(pk, idx, tokenize.token_text(text), ver) for pk, idx, text in rows]

        # ⚠️ executemany는 행마다 서버를 왕복해서 원격 DB에서는 163,407행에
        # 수십 분이 걸린다. VALUES 목록 하나로 묶어 배치당 1회만 왕복한다.
        # `{key}`의 타입을 명시해야 한다 — VALUES의 추론 타입(text)과
        # 컬럼 타입(bigint)이 달라 조인이 안 붙는다.
        key_type = "TEXT" if key == "dataset_id" else "BIGINT"
        execute_values(
            cur,
            f"UPDATE {table} AS t SET token_text = v.tok, tokenizer_ver = v.ver "
            f"FROM (VALUES %s) AS v(k, ci, tok, ver) "
            f"WHERE t.{key} = v.k::{key_type} AND t.chunk_index = v.ci::INTEGER",
            payload,
            template="(%s, %s, %s, %s)",
            page_size=len(payload) or 1,
            fetch=False,
        )
        conn.commit()
        done += len(rows)
        rate = done / max(time.time() - t0, 0.001)
        logger.info("  %s  %d/%d  (%.0f행/초)", table, done, target, rate)

    conn.close()
    return done


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=sorted(TABLES), help="생략하면 전부")
    ap.add_argument("--limit", type=int, help="테이블당 최대 처리 행 수")
    ap.add_argument("--dry-run", action="store_true", help="대상 건수만 센다")
    args = ap.parse_args()

    logger.info("토크나이저: %s\n", tokenize.version())
    targets = [args.source] if args.source else sorted(TABLES)
    total = 0
    for s in targets:
        try:
            total += backfill(s, args.limit, args.dry_run)
        except Exception as e:                      # noqa: BLE001
            # 한 테이블이 실패해도 나머지는 돌린다 — 앞 배치는 이미 커밋돼 있다
            logger.error("%s 실패: %s", s, e)
            return 1
    logger.info("\n합계 %d건", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
