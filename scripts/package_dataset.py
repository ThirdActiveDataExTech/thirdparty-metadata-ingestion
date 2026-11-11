"""데이터셋을 서명된 zip 패키지로 묶고 검증·복원·암호화한다 (C5).

연구개발계획서 3·4차년도 "신뢰성 보장 패키징"/"능동형 패키징".

    <dataset>_<version>.zip
      manifest.json          파일 목록 + SHA-256 + 출처 + 기술통계 + 이력·레퍼런스·점검·복원 정보
      manifest.ed25519.sig   Ed25519 서명(공개키로 누구나 검증) / signer.pub.pem 공개키
      manifest.sig           HMAC-SHA256(공유키가 있을 때)
      data/…                 실제 파일 / recovery/… 복원용 패리티

실행:
    # 키 만들기(사람이 한 번) — 비밀키는 Secret으로, 공개키는 받는 쪽에 공식 경로로 전달
    PYTHONPATH=. python scripts/package_dataset.py keygen --out <디렉터리>
    export PACKAGE_SIGNING_ED25519_KEY="$(cat <디렉터리>/package_signing_ed25519.pem)"

    PYTHONPATH=. python scripts/package_dataset.py build <dataset_id> --from <디렉터리> [--encrypt]
    PYTHONPATH=. python scripts/package_dataset.py verify <패키지.zip> [--pubkey 공개키.pem]
    PYTHONPATH=. python scripts/package_dataset.py repair <손상된.zip> --out <복원.zip>
    PYTHONPATH=. python scripts/package_dataset.py decrypt <패키지.zip.enc> --out <패키지.zip>

암호화 비밀번호는 환경변수 PACKAGE_PASSPHRASE 또는 입력 프롬프트로 받는다(명령줄 인자로 받지 않는다 —
셸 기록·프로세스 목록에 남는다).

⚠️ **검증·복원·복호화는 DB도 네트워크도 쓰지 않는다.** 받는 쪽은 zip과 공개키만 있으면 된다.
   `build`는 출처·기술통계·이력을 채우려고 DB를 읽지만, 없으면 그 칸만 비운 채 만든다.
"""

import argparse
import getpass
import logging
import os
import sys
from pathlib import Path

from src.packaging import builder, envelope, manifest as M, recovery, signing, verify as V

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


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


#: 이력에 담는 최근 수집 실행 수
LINEAGE_RUNS = 20


def lineage_context(dataset_id: str):
    """manifest 1.1의 `lineage`·`reference` 절과 기대 행 수. 실패해도 패키징은 계속한다.

    이력에는 오류 원문을 넣지 않는다(내부 주소·키 일부가 섞일 수 있다). 소유자 계정 ID 대신
    소유 구분(origin)과 발행 기관만 담는다.
    """
    ctx, expected = {}, {}
    try:
        from src.database.db import get_conn
        cur = get_conn().cursor()
        cur.execute(
            "SELECT d.title, d.publisher, d.source_type, d.dataset_origin, d.visibility, d.license, d.rights, "
            "       d.landing_page, d.language, d.accrual_periodicity, d.version, d.created_at, d.updated_at, "
            "       r.registered_at, r.last_collected_at, r.item_count, r.pg_meta_table "
            "FROM dcat_dataset d LEFT JOIN data_registry r USING (dataset_id) WHERE d.dataset_id = %s",
            (dataset_id,))
        row = cur.fetchone()
        if row:
            keys = ("title", "publisher", "source_type", "origin", "visibility", "license", "rights",
                    "landing_page", "language", "accrual_periodicity", "dataset_version", "created_at",
                    "updated_at", "registered_at", "last_collected_at", "item_count")
            ctx["reference"] = {"dataset_id": dataset_id, **{k: _iso(v) for k, v in zip(keys, row[:16])}}
            if row[15] is not None and row[16]:
                expected["items.csv"] = int(row[15])
        cur.execute(
            "SELECT activity_type, agent, triggered_by, started_at, ended_at, status, rows_affected "
            "FROM dcat_provenance WHERE dataset_id = %s ORDER BY started_at DESC LIMIT %s",
            (dataset_id, LINEAGE_RUNS))
        runs = [{"activity": a, "agent": g, "triggered_by": t, "started_at": _iso(s), "ended_at": _iso(e),
                 "status": st, "rows_affected": n} for a, g, t, s, e, st, n in cur.fetchall()]
        if runs:
            ctx["lineage"] = {"collection_runs": runs, "runs_included": len(runs),
                              "note": f"최근 {LINEAGE_RUNS}회까지. 오류 원문은 담지 않는다"}
        cur.close()
    except Exception as e:                        # noqa: BLE001
        logger.warning("이력·레퍼런스를 못 읽었다(패키징은 계속): %s", e)
    return ctx, expected


def _passphrase(confirm: bool) -> str:
    v = os.getenv(envelope.PASSPHRASE_ENV)
    if v:
        return v
    p = getpass.getpass("패키지 비밀번호: ")
    if confirm and getpass.getpass("한 번 더: ") != p:
        raise SystemExit("비밀번호가 서로 다릅니다")
    return p


def cmd_build(args) -> int:
    source, features = _context(args.dataset_id)
    ctx, expected = lineage_context(args.dataset_id)
    out = Path(args.out or f"{args.dataset_id.replace(':', '_')}.zip")
    man = builder.build_package(
        args.dataset_id, Path(args.source_dir), out,
        source=source, features=features, version=args.version,
        context=ctx, with_recovery=not args.no_recovery, expected_rows=expected)
    print(f"\n패키지: {out}")
    print(f"  버전   : {man['version']}")
    print(f"  파일   : {man['file_count']}개 · {man['total_bytes']:,}바이트")
    print(f"  서명   : {' + '.join(man['signer']['algorithms'])}"
          + (f" (지문 {man['signer']['ed25519_fingerprint']})" if 'ed25519_fingerprint' in man['signer'] else ""))
    print(f"  manifest SHA-256: {M.manifest_sha256(man)}")
    print(f"  출처   : {'담김' if source else '비어 있음'} · 통계 {len(features)}종"
          f" · 이력 {len((man.get('lineage') or {}).get('collection_runs', []))}회"
          f" · 복원 정보 {'있음' if man.get('recovery') else '없음'}")
    q = man["quality"]
    print(f"  점검   : 통과 {q['passed']} · 실패 {q['failed']}")
    if args.encrypt:
        enc = Path(str(out) + ".enc")
        envelope.encrypt_file(out, enc, _passphrase(confirm=True))
        out.unlink()
        print(f"  암호화 : {enc} (AES-256-GCM, 비밀번호는 저장하지 않음)")
    return 0


def cmd_verify(args) -> int:
    pub = Path(args.pubkey).read_bytes() if args.pubkey else None
    r = V.verify_package(Path(args.package), pubkey_pem=pub)
    print(f"\n패키지: {args.package}")
    if r.manifest:
        m = r.manifest
        print(f"  데이터셋: {m['dataset_id']}  버전 {m['version']}  (형식 {m['manifest_version']})")
        print(f"  생성    : {m['created_at']}")
        if m.get("source", {}).get("title"):
            print(f"  출처    : {m['source']['title']} / {m['source'].get('publisher')}")
        print(f"  파일    : {m['file_count']}개")
        q = m.get("quality")
        if q:
            print(f"  점검    : 통과 {q['passed']} · 실패 {q['failed']} (만든 쪽 기록)")
    for alg, st in r.signatures.items():
        mark = {"ok": "✅ 유효", "fail": "❌ 불일치", "unchecked": "– 공유키 없음(확인 안 함)"}[st]
        print(f"  서명 {alg:<11}: {mark}")
    if r.signer_fingerprint:
        if r.signer_trusted:
            print(f"  출처 확인: ✅ 주어진 공개키로 확인 (지문 {r.signer_fingerprint})")
        else:
            print(f"  출처 확인: ⚠️ 패키지에 든 공개키로만 확인 — 지문 {r.signer_fingerprint}를 공식 공개키와 대조하세요")
    print(f"  체크섬  : {'✅ 전부 일치' if r.files_ok else '❌ 불일치'}")
    for p in r.problems:
        print(f"    ⚠️ {p}")
    if r.repairable:
        print(f"  복원    : {len(r.repairable)}개 파일 복원 가능 → repair 명령")
    if r.unrepairable:
        print(f"  복원    : {len(r.unrepairable)}개 파일은 복원할 수 없음(다시 받아야 함)")
    print(f"\n{'✅ 검증 통과' if r.ok else '❌ 검증 실패'}")
    return 0 if r.ok else 1


def cmd_repair(args) -> int:
    pub = Path(args.pubkey).read_bytes() if args.pubkey else None
    try:
        r = V.repair_package(Path(args.package), Path(args.out), pubkey_pem=pub)
    except recovery.RecoveryError as e:
        print(f"❌ 복원 실패: {e}")
        return 1
    print(f"{'✅ 복원 후 검증 통과' if r.ok else '❌ 복원 후에도 검증 실패'}: {args.out}")
    return 0 if r.ok else 1


def cmd_decrypt(args) -> int:
    try:
        envelope.decrypt_file(Path(args.package), Path(args.out), _passphrase(confirm=False))
    except envelope.EnvelopeError as e:
        print(f"❌ {e}")
        return 1
    print(f"✅ 복호화: {args.out} — 이어서 verify로 서명·체크섬을 확인하세요")
    return 0


def cmd_keygen(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    priv_path, pub_path = out / "package_signing_ed25519.pem", out / "package_signing_ed25519.pub.pem"
    if priv_path.exists() and not args.force:
        print(f"❌ 이미 있습니다: {priv_path} (덮어쓰려면 --force)")
        return 1
    priv, pub = signing.generate()
    fd = os.open(priv_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(priv)
    pub_path.write_bytes(pub)
    print(f"비밀키: {priv_path} (권한 600 — Secret에 넣은 뒤 이 파일은 안전하게 보관·삭제)")
    print(f"공개키: {pub_path}")
    print(f"지문  : {signing.fingerprint(signing.load_public_key(pub))}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="패키지 생성")
    b.add_argument("dataset_id")
    b.add_argument("--from", dest="source_dir", required=True, help="담을 디렉터리")
    b.add_argument("--out", help="출력 zip 경로")
    b.add_argument("--version", help="버전 문자열 (기본: UTC 타임스탬프)")
    b.add_argument("--encrypt", action="store_true", help="비밀번호로 암호화(*.zip.enc)")
    b.add_argument("--no-recovery", action="store_true", help="복원 정보(패리티)를 넣지 않는다")
    b.set_defaults(func=cmd_build)

    v = sub.add_parser("verify", help="패키지 검증 (DB 불필요)")
    v.add_argument("package")
    v.add_argument("--pubkey", help="공식 경로에서 받은 Ed25519 공개키(PEM) — 주면 출처까지 확인")
    v.set_defaults(func=cmd_verify)

    rp = sub.add_parser("repair", help="손상된 데이터 파일을 복원 정보로 되살린다")
    rp.add_argument("package")
    rp.add_argument("--out", required=True)
    rp.add_argument("--pubkey")
    rp.set_defaults(func=cmd_repair)

    d = sub.add_parser("decrypt", help="암호화 패키지(*.zip.enc)를 푼다")
    d.add_argument("package")
    d.add_argument("--out", required=True)
    d.set_defaults(func=cmd_decrypt)

    k = sub.add_parser("keygen", help="Ed25519 서명 키 쌍을 만든다(사람이 한 번)")
    k.add_argument("--out", required=True, help="키 파일을 쓸 디렉터리")
    k.add_argument("--force", action="store_true")
    k.set_defaults(func=cmd_keygen)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
