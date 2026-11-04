"""영상에 AI 메타데이터(요약·키워드)를 생성한다 (A2 최소선).

연구개발계획서 1·2차년도 "비정형 액티브 메타데이터 **처리**" — 지금까지
STT만 있고 NLP는 없었다.

⚠️ **생성 요약이 아니라 추출 요약이다.** ADR-013이 외부 LLM을 금지했고
   원칙이 "LLM이 없어도 기능이 성립해야 한다"였다. 원문에서 문장을
   고르기만 하므로 hallucination이 없고 출처가 추적된다.

실행:
    PYTHONPATH=. python scripts/generate_ai_meta.py --dataset <id>
    PYTHONPATH=. python scripts/generate_ai_meta.py --all
    PYTHONPATH=. python scripts/generate_ai_meta.py --dataset <id> --dry-run
    PYTHONPATH=. python scripts/generate_ai_meta.py --show <meta_id>
"""

import argparse
import logging
import sys

from src.ai_meta import runner
from src.database.db import get_conn

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")


def show(meta_id: int) -> int:
    cur = get_conn().cursor()
    cur.execute(
        "SELECT v.title, a.ai_summary, a.ai_keywords, a.source_chars, "
        "       a.has_transcript, a.status, a.method "
        "FROM meta_video v LEFT JOIN meta_video_ai a ON a.meta_id = v.id "
        "WHERE v.id = %s", (meta_id,))
    r = cur.fetchone()
    if not r:
        print(f"없는 영상: {meta_id}")
        return 1
    print(f"\n{r[0]}\n" + "─" * 72)
    if r[5] is None:
        print("  AI 메타 없음 — 생성을 먼저 실행하세요.")
        return 0
    print(f"  상태   : {r[5]}  (입력 {r[3]}자{', 자막 포함' if r[4] else ''})")
    print(f"  키워드 : {', '.join(r[2] or [])}")
    print(f"  요약   : {r[1] or '(없음)'}")
    print(f"\n  방법   : {r[6]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", help="이 데이터셋만")
    ap.add_argument("--all", action="store_true", help="영상 데이터셋 전부")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--show", type=int, metavar="META_ID")
    args = ap.parse_args()

    if args.show:
        return show(args.show)
    if not args.dataset and not args.all:
        ap.error("--dataset 또는 --all 중 하나가 필요하다")

    cur = get_conn().cursor()
    if args.all:
        cur.execute("SELECT dataset_id, title FROM dcat_dataset "
                    "WHERE source_type = 'video' ORDER BY title")
        targets = cur.fetchall()
    else:
        cur.execute("SELECT dataset_id, title FROM dcat_dataset WHERE dataset_id = %s",
                    (args.dataset,))
        targets = cur.fetchall()

    total = {"total": 0, "ok": 0, "skipped": 0, "failed": 0}
    for ds, title in targets:
        print(f"\n▶ {title}")
        r = runner.generate_for_dataset(ds, limit=args.limit, dry_run=args.dry_run)
        for k in total:
            total[k] += r[k]
    print(f"\n합계 {total['total']}건 — 생성 {total['ok']} · "
          f"건너뜀 {total['skipped']} · 실패 {total['failed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
