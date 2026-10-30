"""이미 수집한 뉴스·블로그 본문을 다시 긁어 DB와 오브젝트 스토리지를 갱신한다.

**왜 필요한가.** 2026-10-30 이전 수집분은 본문 추출 시 내비·푸터·댓글 위젯이
함께 들어갔다. 외부 매체는 전용 셀렉터가 걸리지 않아 `<article>`/`<p>` 폴백으로
떨어지는데, 그 폴백이 30자 넘는 문단을 모두 가져오기 때문이다.
실측: 뉴스 본문 1,689건 중 300건(17.8%)이 오염.

이 문구는 매체의 모든 기사에 똑같이 들어가므로, 검색의 청크 최대 유사도
집계에서 질의와 무관하게 중간 점수를 내 무관한 기사를 상위로 올린다.

청크 단계의 패턴 필터(`chunker._BOILERPLATE`)로도 가릴 수 있지만 매체마다
문구가 달라 끝이 없다 — 실제로 패턴을 두 번 늘린 뒤 세 번째 변종이 나왔다.
`_strip_non_content()`를 적용한 수집기로 **다시 긁는 것이 근본 해결이다.**

안전장치:
  - 스크래핑 실패(삭제·차단·타임아웃) 시 **기존 본문을 유지한다.** 덮어쓰지 않는다
  - 매 요청 사이에 지연을 둔다(기본 0.5초)
  - --dry-run으로 변경량만 먼저 확인할 수 있다

실행 방법:
    python scripts/rescrape_content.py --source news --dry-run
    python scripts/rescrape_content.py --source news --delay 0.5
    python scripts/rescrape_content.py --source blog --limit 50

끝난 뒤 반드시 재임베딩한다:
    python scripts/backfill_embeddings.py
"""

import argparse
import time

from src.collectors import naver_blog_collector, naver_news_collector
from src.database.db import get_conn
from src.storage import raw_export

SOURCES = {
    "news": {
        "table": "meta_news",
        "url_col": "article_url",
        "select": "SELECT id, dataset_id, article_url, content FROM meta_news WHERE content IS NOT NULL ORDER BY id",
    },
    "blog": {
        "table": "meta_blog",
        "url_col": "post_url",
        "select": "SELECT id, dataset_id, post_url, content, platform, blog_id, log_no "
                  "FROM meta_blog WHERE content IS NOT NULL ORDER BY id",
    },
}


def _fetch(source: str, row) -> str:
    if source == "news":
        return naver_news_collector.fetch_article_content(row[2])
    return naver_blog_collector.fetch_post_content(row[2], row[4], row[5], row[6])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=sorted(SOURCES), required=True)
    ap.add_argument("--limit", type=int, default=None, help="처리할 최대 건수")
    ap.add_argument("--delay", type=float, default=0.5, help="요청 간 지연(초, 기본 0.5)")
    ap.add_argument("--dry-run", action="store_true", help="DB·스토리지를 바꾸지 않고 변경량만 센다")
    args = ap.parse_args()

    spec = SOURCES[args.source]
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(spec["select"])
    rows = cur.fetchall()
    if args.limit:
        rows = rows[: args.limit]

    print(f"{args.source} 본문 {len(rows):,}건 재수집"
          + (" (dry-run — 쓰지 않음)" if args.dry_run else ""))

    changed = failed = same = 0
    shrunk = 0
    for i, row in enumerate(rows, 1):
        item_id, dataset_id, url, old = row[0], row[1], row[2], row[3]
        try:
            new = _fetch(args.source, row)
        except Exception:
            new = None

        if not new:
            failed += 1          # 기존 본문을 그대로 둔다
        elif new == old:
            same += 1
        else:
            changed += 1
            if len(new) < len(old):
                shrunk += 1
            if not args.dry_run:
                cur.execute(
                    f"UPDATE {spec['table']} SET content = %s, has_content = TRUE WHERE id = %s",
                    (new, item_id),
                )
                conn.commit()
                try:
                    raw_export.write_article_content(dataset_id, args.source, item_id, new)
                except Exception as e:
                    print(f"  [{item_id}] 스토리지 기록 실패(DB는 갱신됨): {e}")

        if i % 100 == 0:
            print(f"  {i:,}/{len(rows):,}  변경 {changed:,} · 동일 {same:,} · 실패 {failed:,}")
        if args.delay:
            time.sleep(args.delay)

    print(f"\n완료 — 변경 {changed:,} (그중 짧아짐 {shrunk:,}) · 동일 {same:,} · 실패 {failed:,}")
    if changed and not args.dry_run:
        print("다음: python scripts/backfill_embeddings.py")
    cur.close()


if __name__ == "__main__":
    main()
