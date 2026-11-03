"""데이터셋 특징 메타를 산출해 meta_feature에 저장한다 (B1).

연구개발계획서 1차년도 "액티브 메타데이터 기반 데이터 특징 추출 및 분석 기술"
/ SW 모듈 "데이터 특징 추출 및 분석 모듈(모비젠)"의 최소선 구현이다.

왜 필요한가: 데이터셋 레벨 메타데이터가 너무 빈약해 B2 관계 분석의 입력이 되지
못한다 — 등록 키워드 평균 2~3개, description 평균 24~36자, 300쌍 중 22쌍(7.3%)만
키워드를 공유한다(docs/database/metadata_quality_probe.md). 신호는 아이템
8,273건 쪽에 있고, 이 스크립트가 그걸 데이터셋 레벨로 끌어올린다.

실행:
    PYTHONPATH=. python scripts/extract_features.py                 # 전체
    PYTHONPATH=. python scripts/extract_features.py --dry-run       # 계산만
    PYTHONPATH=. python scripts/extract_features.py --dataset <id>  # 한 건만 저장
    PYTHONPATH=. python scripts/extract_features.py --show <id>     # 저장된 특징 보기

⚠️ `--dataset`을 줘도 **집계는 전부 읽는다.** TF-IDF의 IDF가 "다른 데이터셋에도
   나오는 말인가"라서 한 데이터셋만 떼어 계산할 수 없다. 저장만 한 건에 한다.
"""

import argparse
import json
import logging
import sys

from src.analysis.features import extract
from src.database.db import get_conn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s",
                    datefmt="%H:%M:%S")


def show(dataset_id: str) -> int:
    cur = get_conn().cursor()
    cur.execute("SELECT title, source_type FROM dcat_dataset WHERE dataset_id = %s", (dataset_id,))
    row = cur.fetchone()
    if not row:
        print(f"없는 데이터셋: {dataset_id}")
        return 1
    print(f"\n{row[0]}  [{row[1]}]\n{dataset_id}\n" + "─" * 70)
    cur.execute("SELECT feature_name, value, method, computed_at FROM meta_feature "
                "WHERE dataset_id = %s AND scope = 'dataset' ORDER BY feature_name", (dataset_id,))
    rows = cur.fetchall()
    if not rows:
        print("  저장된 특징 없음 — scripts/extract_features.py 를 먼저 실행하세요.")
        return 0
    for name, value, method, at in rows:
        if name == "top_keywords":
            terms = " ".join(f"{d['term']}({d['tfidf']:.0f})" for d in value[:15])
            print(f"  {name:<20} {terms}")
        elif name == "representative_text":
            print(f"  {name:<20}")
            for t in value:
                print(f"  {'':<20} · {t[:70]}")
        else:
            print(f"  {name:<20} {json.dumps(value, ensure_ascii=False)}")
    print(f"\n  산출 방법: {rows[0][2]}   시각: {rows[0][3]:%Y-%m-%d %H:%M}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", help="이 데이터셋만 저장 (집계는 전부 읽는다)")
    ap.add_argument("--dry-run", action="store_true", help="계산만 하고 저장하지 않는다")
    ap.add_argument("--show", metavar="DATASET_ID", help="저장된 특징을 보여준다")
    args = ap.parse_args()

    if args.show:
        return show(args.show)
    r = extract.extract(dataset_id=args.dataset, dry_run=args.dry_run)
    print(f"\n데이터셋 {r['datasets']}개 · 특징 {r['features']}행 · 저장 {r['written']}행")
    return 0


if __name__ == "__main__":
    sys.exit(main())
