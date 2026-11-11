"""격리 환경 수집 번들 — 현장에서 만들고(collect), 플랫폼에서 들인다(ingest). (A1 · 3차년도)

    # [현장] 에이전트 키(한 번) → 공개키를 플랫폼 configs/agents/<이름>.pub.pem 으로 전달
    PYTHONPATH=. python scripts/package_dataset.py keygen --out ~/agent-key
    export AGENT_SIGNING_KEY="$(cat ~/agent-key/package_signing_ed25519.pem)"

    # [현장] 수집 → 서명된 번들(DB·플랫폼 접속 없음)
    PYTHONPATH=. python scripts/agent_bundle.py collect <파이프라인 이름> --out bundle.zip [--limit N] [--agent-id 현장A]

    # [플랫폼] 확인만 / 반입
    PYTHONPATH=. python scripts/agent_bundle.py ingest bundle.zip --dry-run
    PYTHONPATH=. python scripts/agent_bundle.py ingest bundle.zip
    # 또는 관리자 API: POST /v1/console/agent-bundles (multipart file)

설계는 src/agent/bundle.py 머리말.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from src.agent import bundle as B

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")


def cmd_collect(args) -> int:
    try:
        man = B.collect_bundle(args.pipeline, Path(args.out), B.agent_key_from_env(),
                               limit=args.limit, agent_id=args.agent_id)
    except B.BundleError as e:
        print(f"❌ {e}")
        return 1
    b = man["bundle"]
    print(f"\n번들: {args.out}")
    print(f"  파이프라인: {b['pipeline']} → {b['dataset_id']}")
    print(f"  원천      : {b['source']} ({b['adapter_kind']})")
    print(f"  수집      : 원본 {b['raw_count']}건 → 정규화 {b['row_count']}행")
    print(f"  서명      : Ed25519 지문 {man['signer']['ed25519_fingerprint']}")
    return 0


def cmd_ingest(args) -> int:
    try:
        r = B.ingest_bundle(Path(args.bundle), dry_run=args.dry_run)
    except B.BundleError as e:
        print(f"❌ 반입 거부: {e}")
        return 1
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
    print("\n✅ " + ("확인 완료(쓰지 않음)" if args.dry_run else "반입 완료"))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect", help="[현장] 수집해 서명된 번들을 만든다")
    c.add_argument("pipeline")
    c.add_argument("--out", required=True)
    c.add_argument("--limit", type=int)
    c.add_argument("--agent-id", help="현장 표시(이력에 남는다). 개인 이름은 쓰지 않는다")
    c.set_defaults(func=cmd_collect)
    i = sub.add_parser("ingest", help="[플랫폼] 번들을 확인하고 들인다")
    i.add_argument("bundle")
    i.add_argument("--dry-run", action="store_true")
    i.set_defaults(func=cmd_ingest)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
