#!/usr/bin/env python3
"""등록된 시나리오 데이터셋을 순서대로 수집한다.

실패해도 멈추지 않고 끝까지 돌린 뒤 결과를 모아 보고한다 — 한 소스의 문제가
다른 소스 점검을 막지 않게 한다.

사용:
    PYTHONPATH=. python scripts/scenarios/run_collection.py --only shopping_insight
    PYTHONPATH=. python scripts/scenarios/run_collection.py          # 전부
"""
import argparse
import logging
import sys
import time
import traceback

from src.database.db import get_conn
from src.main import run_dataset


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="source_type 하나만")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)

    conn = get_conn()
    cur = conn.cursor()
    q = "SELECT dataset_id, title, source_type FROM dcat_dataset"
    params = []
    if args.only:
        q += " WHERE source_type = %s"
        params.append(args.only)
    q += " ORDER BY source_type, dataset_id"
    cur.execute(q, params)
    rows = cur.fetchall()
    conn.close()

    ok, fail = [], []
    for did, title, st in rows:
        t0 = time.time()
        try:
            run_dataset(did, triggered_by="scenario-check")
            el = time.time() - t0
            ok.append((did, title, st, el))
            print(f"  ✅ {st:<18} {title[:26]:<26} {el:>6.1f}초  {did}")
        except Exception as e:
            el = time.time() - t0
            fail.append((did, title, st, f"{type(e).__name__}: {e}", traceback.format_exc()))
            print(f"  ❌ {st:<18} {title[:26]:<26} {el:>6.1f}초  {type(e).__name__}: {str(e)[:60]}")
        sys.stdout.flush()

    print(f"\n  성공 {len(ok)}건 / 실패 {len(fail)}건")
    for did, title, st, msg, tb in fail:
        print(f"\n=== [{st}] {title} 실패 ===\n{tb[-900:]}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
