"""데이터셋 간 관계를 산출해 dcat_dataset_relation에 적재한다 (B2).

연구개발계획서 1차년도 "데이터 패턴 모델링 기반 데이터 관계 분석 기술" /
2차년도 "네트워크 생성 및 관계 분석"의 최소선이다.

두 축을 따로 재고 상위 K만 남긴다 — 합치지 않는 이유와 임계값을 쓰지 않는
이유는 src/analysis/relations/similarity.py 머리말 참조.

실행:
    PYTHONPATH=. python scripts/build_relations.py                # 산출·적재
    PYTHONPATH=. python scripts/build_relations.py --dry-run      # 계산만
    PYTHONPATH=. python scripts/build_relations.py --top-k 10     # 이웃 수 조정
    PYTHONPATH=. python scripts/build_relations.py --show <id>    # 이웃 조회

⚠️ 입력은 meta_feature다. `scripts/extract_features.py`(B1)를 먼저 돌려야 한다.
"""

import argparse
import logging
import sys
from collections import Counter

from src.analysis.relations import similarity, store
from src.database.db import get_conn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s",
                    datefmt="%H:%M:%S")


def show(dataset_id: str) -> int:
    cur = get_conn().cursor()
    cur.execute("SELECT title FROM dcat_dataset WHERE dataset_id = %s", (dataset_id,))
    row = cur.fetchone()
    if not row:
        print(f"없는 데이터셋: {dataset_id}")
        return 1
    print(f"\n{row[0]}\n{dataset_id}\n" + "─" * 78)
    rows = store.neighbours(dataset_id, limit=30)
    if not rows:
        print("  관계 없음 — scripts/build_relations.py 를 먼저 실행하세요.")
        return 0
    for rt in sorted({r["relation_type"] for r in rows}):
        print(f"\n  [{rt}]")
        for r in [x for x in rows if x["relation_type"] == rt]:
            print(f"    {r['score']:.4f}  {r['title'][:34]:<36} ({r['source_type']})")
            ev = r["evidence"]
            if ev.get("shared_keywords"):
                print(f"            공유 {ev['shared_count']}개"
                      f" · 자카드 {ev['jaccard']}: {' '.join(ev['shared_keywords'][:6])}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top-k", type=int, default=similarity.TOP_K,
                    help=f"데이터셋당 이웃 수 (기본 {similarity.TOP_K})")
    ap.add_argument("--dry-run", action="store_true", help="계산만 하고 적재하지 않는다")
    ap.add_argument("--show", metavar="DATASET_ID", help="저장된 이웃을 보여준다")
    args = ap.parse_args()

    if args.show:
        return show(args.show)

    rows = similarity.build(args.top_k)
    if not rows:
        print("\n산출된 관계 없음 — B1(extract_features.py)을 먼저 실행했는지 확인하세요.")
        return 0

    by_type = Counter(r["relation_type"] for r in rows)
    print(f"\n산출 {len(rows)}건: " + " · ".join(f"{k} {v}" for k, v in sorted(by_type.items())))
    if args.dry_run:
        print("dry-run — 적재하지 않는다")
        return 0

    r = store.replace(rows)
    print(f"적재: 삭제 {r['deleted']} · 추가 {r['written']} · 검토완료 보존 {r['kept']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
