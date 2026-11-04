"""스펙(YAML)으로 선언한 파이프라인을 실행한다 (C3 최소선).

연구개발계획서 2차년도 "템플릿 기반 파이프라인 구성" 〔SW 모듈: 모비젠〕.
파이프라인을 **코드가 아니라 선언으로** 만든다.

    configs/pipelines/<이름>.yaml
      source_spec   A1 어댑터 스펙 (configs/sources/*.yaml)
      dataset_id    어느 데이터셋에 넣을지
      target        테이블 · 컬럼 매핑 · 충돌 키
      steps         collect → normalize → store → postprocess

실행:
    PYTHONPATH=. python scripts/run_pipeline.py --list
    PYTHONPATH=. python scripts/run_pipeline.py naver_news_adapter --dry-run
    PYTHONPATH=. python scripts/run_pipeline.py naver_news_adapter --limit 60

기존 `src/pipelines/*.py` 5종과 **공존한다.** 점진 이관이 목표선이고,
지금 갈아치우면 검증된 것을 잃는다.
"""

import argparse
import logging
import sys

from src.pipeline_engine import runner

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pipeline", nargs="?", help="파이프라인 이름 또는 YAML 경로")
    ap.add_argument("--list", action="store_true", help="쓸 수 있는 파이프라인")
    ap.add_argument("--limit", type=int, help="수집 상한 (스펙 값을 덮어쓴다)")
    ap.add_argument("--dry-run", action="store_true", help="DB에 쓰지 않는다")
    args = ap.parse_args()

    if args.list or not args.pipeline:
        names = runner.available()
        print("\n파이프라인:")
        for n in names:
            spec = runner.load(n)
            print(f"  {n:<24} → {spec['target']['table']}  ({spec['dataset_id']})")
        if not names:
            print("  (configs/pipelines/ 가 비어 있다)")
        return 0

    r = runner.run(args.pipeline, limit=args.limit, dry_run=args.dry_run)
    print(f"\n[{r['pipeline']}] → {r['dataset_id']}")
    for step, info in r["steps"].items():
        secs = info.pop("seconds", None)
        if "error" in info:
            print(f"  ❌ {step:<12} {info['error'][:70]}")
        else:
            print(f"  ✅ {step:<12} {info}  ({secs}초)")
    print(f"\n{'성공' if r['ok'] else '실패'} — 총 {r['seconds']}초")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
