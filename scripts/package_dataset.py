"""데이터셋을 서명된 zip 패키지로 묶고 검증한다 (C5).

연구개발계획서 3·4차년도 "신뢰성 보장 패키징"/"능동형 패키징"의 최소선이다.

    <dataset>_<version>.zip
      manifest.json   파일 목록 + SHA-256 + 출처 + B1 기술통계
      manifest.sig    manifest의 HMAC-SHA256
      data/…          실제 파일

실행:
    export PACKAGE_SIGNING_KEY="$(openssl rand -base64 32)"
    PYTHONPATH=. python scripts/package_dataset.py build <dataset_id> --from <디렉터리>
    PYTHONPATH=. python scripts/package_dataset.py verify <패키지.zip>

⚠️ **검증은 DB도 네트워크도 쓰지 않는다.** 받는 쪽은 zip과 공유키만 있으면 된다.
   `build`는 출처·기술통계를 채우려고 DB를 읽지만, 없으면 그 칸만 비운 채 만든다.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from src.packaging import builder, manifest as M, verify as V

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
logger = logging.getLogger(__name__)


def _context(dataset_id: str):
    """출처와 B1 기술통계를 DB에서 긁어온다. 실패해도 패키징은 계속한다."""
    source, features = {}, {}
    try:
        from src.database.db import get_conn
        cur = get_conn().cursor()
        cur.execute(
            "SELECT title, description, publisher, license, source_type, "
            "       temporal_start, temporal_end "
            "FROM dcat_dataset WHERE dataset_id = %s", (dataset_id,))
        row = cur.fetchone()
        if row:
            source = {
                "title": row[0], "description": row[1], "publisher": row[2],
                "license": row[3], "source_type": row[4],
                "temporal_start": row[5].isoformat() if row[5] else None,
                "temporal_end": row[6].isoformat() if row[6] else None,
            }
        cur.execute(
            "SELECT feature_name, value FROM meta_feature "
            "WHERE dataset_id = %s AND scope = 'dataset' "
            "  AND feature_name IN ('item_count','chunk_count','text_length',"
            "                       'collected_period','top_keywords')", (dataset_id,))
        features = {n: v for n, v in cur.fetchall()}
        cur.close()
    except Exception as e:                        # noqa: BLE001
        # 패키징은 파일 작업이다. DB가 없다고 멈출 이유가 없다 —
        # 그 칸만 비고, manifest는 여전히 체크섬·서명으로 유효하다
        logger.warning("출처·통계를 못 읽었다(패키징은 계속): %s", e)
    return source, features


def cmd_build(args) -> int:
    source, features = _context(args.dataset_id)
    out = Path(args.out or f"{args.dataset_id.replace(':', '_')}.zip")
    man = builder.build_package(
        args.dataset_id, Path(args.source_dir), out,
        source=source, features=features, version=args.version)
    print(f"\n패키지: {out}")
    print(f"  버전   : {man['version']}")
    print(f"  파일   : {man['file_count']}개 · {man['total_bytes']:,}바이트")
    print(f"  manifest SHA-256: {M.manifest_sha256(man)}")
    print(f"  출처   : {'담김' if source else '비어 있음'}"
          f" · 통계 {len(features)}종")
    return 0


def cmd_verify(args) -> int:
    r = V.verify_package(Path(args.package))
    print(f"\n패키지: {args.package}")
    if r.manifest:
        m = r.manifest
        print(f"  데이터셋: {m['dataset_id']}  버전 {m['version']}")
        print(f"  생성    : {m['created_at']}")
        if m.get("source", {}).get("title"):
            print(f"  출처    : {m['source']['title']} / {m['source'].get('publisher')}")
        print(f"  파일    : {m['file_count']}개")
    print(f"  서명    : {'✅ 유효' if r.signature_ok else '❌ 불일치'}")
    print(f"  체크섬  : {'✅ 전부 일치' if r.files_ok else '❌ 불일치'}")
    for p in r.problems:
        print(f"    ⚠️ {p}")
    print(f"\n{'✅ 검증 통과' if r.ok else '❌ 검증 실패'}")
    return 0 if r.ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="패키지 생성")
    b.add_argument("dataset_id")
    b.add_argument("--from", dest="source_dir", required=True, help="담을 디렉터리")
    b.add_argument("--out", help="출력 zip 경로")
    b.add_argument("--version", help="버전 문자열 (기본: UTC 타임스탬프)")
    b.set_defaults(func=cmd_build)

    v = sub.add_parser("verify", help="패키지 검증 (DB 불필요)")
    v.add_argument("package")
    v.set_defaults(func=cmd_verify)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
