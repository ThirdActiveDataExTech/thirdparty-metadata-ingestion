"""기존 손 수집기와 어댑터 스펙이 같은 결과를 내는지 실제 원천으로 대조한다 (A1 목표선 이관 검증).

    PYTHONPATH=. python scripts/verify_adapter_migration.py blog --query "홈트레이닝"
    PYTHONPATH=. python scripts/verify_adapter_migration.py shopping --category 50000000:패션의류 --days 30

DB에 쓰지 않는다 — 원천 API만 읽는다. 일치하면 0, 다르면 1로 끝난다.
"""

import argparse
import sys
from datetime import date, timedelta

from src.collectors.adapters.rest_json import RestJsonCollector
from src.common import config


def blog(args) -> int:
    from src.collectors import naver_blog_collector as old
    a = RestJsonCollector.from_file("configs/sources/naver_blog.yaml")
    new = [a.normalize(r) for r in a.fetch(query={"query": args.query})]
    ref = old.search_all(config.require_env("NAVER_CLIENT_ID"), config.require_env("NAVER_CLIENT_SECRET"),
                         args.query, max_pages=3, display=100, sort="date")
    old_links = [r["link"] for r in ref]
    new_links = [r["post_url"] for r in new]
    both = set(old_links) & set(new_links)
    print(f"블로그 '{args.query}': 기존 {len(old_links)}건 · 어댑터 {len(new_links)}건 · 겹침 {len(both)} · "
          f"어댑터만 {len(set(new_links) - set(old_links))} · 기존만 {len(set(old_links) - set(new_links))}")
    titles_ok = all(old._strip_b_tags(o["title"]) == n["title"] for o, n in zip(ref, new) if o["link"] == n["post_url"])
    print(f"  같은 순서의 제목 정리 결과 일치: {titles_ok}")
    return 0 if set(old_links) == set(new_links) and titles_ok else 1


def shopping(args) -> int:
    from src.collectors import naver_shopping_collector as old
    cid, name = args.category.split(":", 1)
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=args.days)
    q = {"startDate": start.isoformat(), "endDate": end.isoformat(), "timeUnit": "date",
         "category": [{"name": name, "param": [cid]}], "gender": "", "ages": [str(args.age)]}
    a = RestJsonCollector.from_file("configs/sources/naver_shopping_insight.yaml")
    rows = [a.normalize(r) for r in a.fetch(query=q)]
    new = {}
    for r in rows:
        new.setdefault(r["category"], {})[r["period"]] = r["ratio"]
    data = old.fetch_insight(config.require_env("NAVER_CLIENT_ID"), config.require_env("NAVER_CLIENT_SECRET"),
                             start.isoformat(), end.isoformat(), "date", [(cid, name)], "", str(args.age))
    ref = old.parse_response(data or {})
    same = ref == new
    print(f"쇼핑인사이트 {name}({cid}) {start}~{end} 연령 {args.age}: 기존 {sum(len(v) for v in ref.values())}점 · "
          f"어댑터 {len(rows)}행 · 값 일치: {same}")
    return 0 if same and rows else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("blog")
    b.add_argument("--query", default="홈트레이닝")
    b.set_defaults(func=blog)
    s = sub.add_parser("shopping")
    s.add_argument("--category", default="50000000:패션의류")
    s.add_argument("--days", type=int, default=30)
    s.add_argument("--age", default="30")
    s.set_defaults(func=shopping)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
