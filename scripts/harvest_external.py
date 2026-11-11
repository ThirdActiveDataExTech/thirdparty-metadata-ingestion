"""외부 포털(CKAN·SDMX)에서 데이터셋 메타를 수집해 내부 카탈로그에 합친다 (C6).

연구개발계획서 3차년도 "탐색 확장·통합 구성".
**메타데이터만 가져온다** — 원본 파일은 복제하지 않고 `landing_page`로 가리킨다.

실행:
    PYTHONPATH=. python scripts/harvest_external.py --portal https://open.canada.ca/data \
        --query semiconductor --max 30
    PYTHONPATH=. python scripts/harvest_external.py --portal ... --dry-run
    PYTHONPATH=. python scripts/harvest_external.py --embed     # 검색에 합류시킨다

    # SDMX 통계 포털(OECD·Eurostat·ECB 또는 --endpoint) — 데이터플로(통계표) 단위
    PYTHONPATH=. python scripts/harvest_external.py --sdmx oecd --query "household income" --max 20 --dry-run

⚠️ 들여온 뒤 `--embed`를 돌려야 /v1/search 에 나온다. 임베딩이 없으면
   카탈로그 목록에는 보이지만 검색에는 안 걸린다 — 오류가 아니라 조용한 누락이다.
"""

import argparse
import logging
import sys

from src.federation import ckan, sdmx

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--portal", default="https://open.canada.ca/data",
                    help="CKAN 포털 주소 (기본: 캐나다 공개데이터 포털)")
    ap.add_argument("--query", default="*:*", help="검색어 (기본: 전체)")
    ap.add_argument("--max", type=int, default=50, help="최대 건수")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--embed", action="store_true",
                    help="적재 후 임베딩까지 — 이걸 해야 검색에 나온다")
    ap.add_argument("--sdmx", metavar="포털", help=f"SDMX 포털에서 가져온다 ({', '.join(sorted(sdmx.PRESETS))} 또는 임의 이름+--endpoint)")
    ap.add_argument("--endpoint", help="SDMX REST 주소(--sdmx와 함께, 알려진 포털이 아닐 때)")
    ap.add_argument("--agency", help="SDMX 기관 ID(기본: 포털 설정)")
    ap.add_argument("--visibility", default="ORG", choices=["PUBLIC", "ORG", "PRIVATE"],
                    help="새로 들어오는 행의 공개 범위(기본 ORG — 이미 있는 행은 바꾸지 않는다)")
    args = ap.parse_args()

    if args.sdmx:
        rows = sdmx.harvest(args.sdmx, "" if args.query == "*:*" else args.query, max_records=args.max,
                            base=args.endpoint, agency=args.agency)
    else:
        rows = ckan.harvest(args.portal, args.query, max_records=args.max)
    if not rows:
        print("가져온 것이 없다 — 포털 주소와 검색어를 확인하라.")
        return 1
    r = ckan.store(rows, dry_run=args.dry_run, visibility=args.visibility)
    print(f"\n조회 {r['fetched']}건 · 적재 {r['stored']}건  (origin=external)")
    for row in rows[:3]:
        print(f"  {row['title'][:62]}")

    if args.embed and not args.dry_run:
        from src.embedding import sync
        s = sync.sync("dcat_dataset")
        print(f"\n임베딩: 검사 {s['checked']} · 재생성 {s['items']}건 "
              f"(청크 {s['chunks']})")
        print("  → /v1/search?source=dataset 에서 함께 검색된다")
    elif not args.dry_run:
        print("\n⚠️ --embed 를 돌려야 검색에 나온다 (카탈로그 목록에는 이미 보인다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
