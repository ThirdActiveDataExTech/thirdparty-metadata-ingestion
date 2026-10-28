#!/usr/bin/env python3
"""기존 데이터의 임베딩을 일괄 생성한다.

2026-10-28부터 수집 파이프라인이 임베딩을 자동 동기화하지만, 그 전에 쌓인
데이터는 그대로다. 이 스크립트로 한 번 따라잡는다.

증분이므로 중단했다 다시 돌려도 이어서 처리된다.
scripts/embed_*.py 4종을 대체한다(그쪽은 매번 전량 DELETE 후 재생성이었다).

사용:
    PYTHONPATH=. python scripts/backfill_embeddings.py              # 전부
    PYTHONPATH=. python scripts/backfill_embeddings.py --spec meta_news
    PYTHONPATH=. python scripts/backfill_embeddings.py --limit 1000 # 나눠 돌리기
    PYTHONPATH=. python scripts/backfill_embeddings.py --dry-run    # 대상 건수만
"""
import argparse
import logging
import sys
import time

from src.database.db import get_conn
from src.embedding import sync

SPECS = ["dcat_dataset", "meta_video", "meta_news", "meta_blog"]


def pending_count(spec: str) -> tuple:
    """(전체, 임베딩 있음) — 모델을 올리지 않고 DB만으로 센다."""
    base, vec, key, cols, _ = sync._SPECS[spec]
    src_key = cols.split(",")[0].strip()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT count(*) FROM {base}")
        total = cur.fetchone()[0]
        cur.execute(f"SELECT count(*) FROM {base} b JOIN {vec} v ON v.{key} = b.{src_key}")
        return total, cur.fetchone()[0]
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", choices=SPECS, help="지정 안 하면 전부")
    ap.add_argument("--limit", type=int, help="한 번에 인코딩할 최대 건수")
    ap.add_argument("--dry-run", action="store_true", help="대상 건수만 보고 끝낸다")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="  %(message)s")

    targets = [args.spec] if args.spec else SPECS
    print("=== 현황 ===")
    for s in targets:
        total, has = pending_count(s)
        print(f"  {s:<16} {total:>7,}행 중 임베딩 {has:>7,}건 "
              f"(커버리지 {has * 100 // max(total, 1):>3}%)")
    if args.dry_run:
        return 0

    print("\n=== 생성 ===")
    grand = 0
    for s in targets:
        t0 = time.time()
        r = sync.sync(s, limit=args.limit)
        el = time.time() - t0
        rate = f"{r['embedded'] / el:.0f}건/초" if el > 0 and r["embedded"] else "-"
        print(f"  {s:<16} 생성 {r['embedded']:>7,} / 검사 {r['checked']:>7,} "
              f"({el:>6.1f}초, {rate})")
        grand += r["embedded"]

    print("\n=== 결과 ===")
    for s in targets:
        total, has = pending_count(s)
        flag = "" if has == total else f"  ← {total - has:,}건 남음"
        print(f"  {s:<16} {has:>7,}/{total:>7,}  커버리지 {has * 100 // max(total, 1):>3}%{flag}")
    print(f"\n  총 {grand:,}건 생성")
    return 0


if __name__ == "__main__":
    sys.exit(main())
