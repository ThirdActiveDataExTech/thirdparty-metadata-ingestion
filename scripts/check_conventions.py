#!/usr/bin/env python3
"""현재 데이터가 2026-10-28에 정한 식별자·경로 규칙을 전부 따르는지 전수 점검한다.

규칙 출처: docs/database/dataset_id_urn_migration.md §6·§7
            docs/adr/014_Schema_Ownership_And_Change_Control.md

검사하는 것 (DB → S3 → JSON-LD 순):
  A. dataset_id — URN 형식, 길이, 네임스페이스, source_type 접두 규칙
  B. external_ids — 형식, video 채널키, 집합 해시, sha256- 접두, legacy 보존
  C. 자식 테이블 — 구 slug 잔존 여부
  D. FK — dataset_id 참조 FK가 전부 ON UPDATE CASCADE인가
  E. S3 경로 — data_registry 값이 코드가 만드는 경로와 같은가
  F. S3 실물 — 실제 객체가 레지스트리 경로 아래 있는가
  G. JSON-LD — @id와 adms:identifier가 DB와 일치하는가

사용:
    PYTHONPATH=. python scripts/check_conventions.py
    PYTHONPATH=. python scripts/check_conventions.py --no-s3   # S3 접속 없이 A~D만

읽기 전용이다. 아무것도 바꾸지 않는다.
"""
import json
import re
import sys

from src.database.db import get_conn
from src.storage.s3_client import storage_key
from scripts.register_dataset import (
    _SOURCE_META, _urn_key_prefix, subject_set_hash, normalize_subject_key,
)

URN_RE = re.compile(r"^urn:[a-z0-9]+:[a-z0-9_]+$")
EXT_RE = re.compile(r"^[a-z0-9_-]+:.+$")

_fail: list = []
_warn: list = []


def fail(check: str, msg: str) -> None:
    _fail.append(f"{check}: {msg}")


def warn(check: str, msg: str) -> None:
    _warn.append(f"{check}: {msg}")


def section(title: str) -> None:
    print(f"\n{'─' * 70}\n{title}\n{'─' * 70}")


def ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def bad(msg: str) -> None:
    print(f"  ❌ {msg}")


def main() -> int:
    use_s3 = "--no-s3" not in sys.argv
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT dataset_id, source, source_type, subjects, external_ids
             FROM dcat_dataset ORDER BY dataset_id"""
    )
    rows = cur.fetchall()
    print(f"점검 대상: dcat_dataset {len(rows)}건")

    # ── A. dataset_id ───────────────────────────────────────────────────────
    section("A. dataset_id — URN 형식·네임스페이스·source_type 접두")
    for did, src, st, _subj, _ext in rows:
        if not URN_RE.match(did):
            fail("A-1", f"{did} — URN 형식 위반")
            continue
        if len(did) > 100:
            fail("A-2", f"{did} — {len(did)}자, 상한 100 초과")
        ns = did.split(":")[1]
        want_ns = _SOURCE_META[st]["urn_namespace"]
        if ns != want_ns:
            fail("A-3", f"{did} — 네임스페이스 {ns!r}, source_type={st}이면 {want_ns!r}이어야 함")
        if ns != src.lower():
            fail("A-4", f"{did} — 네임스페이스 {ns!r} ≠ source {src!r}의 소문자")
        body = did.split(":", 2)[2]
        prefix = _urn_key_prefix(st)
        if prefix and not (body.startswith(prefix) or body == st):
            fail("A-5", f"{did} — {ns} 네임스페이스에는 source_type 접두 {prefix!r}가 필요")
        if not prefix and body.startswith(st + "_"):
            warn("A-6", f"{did} — 네임스페이스가 source_type을 이미 결정하는데 접두가 붙어 있음")
    for code, label in [("A-1", "URN 형식"), ("A-2", "길이 상한"), ("A-3", "네임스페이스↔source_type"),
                        ("A-4", "네임스페이스↔source"), ("A-5", "source_type 접두")]:
        n = sum(1 for f in _fail if f.startswith(code))
        (ok if n == 0 else bad)(f"{label}: {len(rows) - n}/{len(rows)}")
    cur.execute("SELECT max(length(dataset_id)) FROM dcat_dataset")
    print(f"     최대 길이 {cur.fetchone()[0]}자 / 100자")

    # ── B. external_ids ─────────────────────────────────────────────────────
    section("B. external_ids — 형식·채널키·집합해시·sha256 접두·legacy 보존")
    for did, src, st, subj, ext in rows:
        if not isinstance(ext, list):
            fail("B-1", f"{did} — 배열이 아님")
            continue
        for e in ext:
            if not isinstance(e, str) or not EXT_RE.match(e):
                fail("B-1", f"{did} — 원소 {e!r}가 '네임스페이스:값' 형식이 아님")
        if not any(e.startswith("legacy:") for e in ext):
            fail("B-2", f"{did} — legacy slug 없음")

        if st == "video":
            chans = subj.get("channels", []) if isinstance(subj, dict) else (subj or [])
            want = {f"youtube:{c}" for c in chans if c}
            got = {e for e in ext if e.startswith("youtube:")}
            if want != got:
                fail("B-3", f"{did} — 채널키 불일치 기대={sorted(want)} 실제={sorted(got)}")
            if any("sha256-" in e for e in ext):
                fail("B-4", f"{did} — video에 집합 해시가 붙어 있음(채널 ID는 원천 발급 키다)")
        else:
            terms = subj if isinstance(subj, list) else []
            hashes = [e for e in ext if e.startswith(f"{src.lower()}:{st}:")]
            if not terms:
                if hashes:
                    fail("B-5", f"{did} — subjects가 비었는데 해시가 있음")
                continue
            want = f"{src.lower()}:{st}:{subject_set_hash(terms)}"
            if hashes != [want]:
                fail("B-5", f"{did} — 해시 불일치 기대={want} 실제={hashes}"
                            f" (정규화={normalize_subject_key(terms)[:50]})")
            if not all("sha256-" in h for h in hashes):
                fail("B-6", f"{did} — 해시에 sha256- 접두 없음: {hashes}")
    for code, label in [("B-1", "형식 '네임스페이스:값'"), ("B-2", "legacy slug 보존"),
                        ("B-3", "video 채널키 ↔ subjects"), ("B-4", "video에 해시 없음"),
                        ("B-5", "집합 해시 ↔ subjects"), ("B-6", "sha256- 접두")]:
        n = sum(1 for f in _fail if f.startswith(code))
        (ok if n == 0 else bad)(f"{label}: 위반 {n}건")

    # 오탐 방지가 실제로 되는지 — 부분 겹침 쌍이 서로 다른 해시인가
    cur.execute(
        """SELECT a.dataset_id, b.dataset_id, count(*)
             FROM dcat_dataset a, jsonb_array_elements_text(a.external_ids) ax,
                  dcat_dataset b, jsonb_array_elements_text(b.external_ids) bx
            WHERE a.dataset_id < b.dataset_id AND ax = bx
              AND ax NOT LIKE 'legacy:%'
            GROUP BY 1, 2 ORDER BY 1, 2"""
    )
    pairs = cur.fetchall()
    print("\n  external_ids가 겹치는 데이터셋 쌍 (중복 판정 대상):")
    if pairs:
        for a, b, n in pairs:
            print(f"     {a}  ↔  {b}   ({n}개 겹침)")
    else:
        print("     (없음)")

    # ── C. 자식 테이블 구 slug ──────────────────────────────────────────────
    section("C. 자식 테이블 — 구 slug 잔존")
    tables = ["meta_video", "meta_news", "meta_blog", "meta_shopping_insight",
              "meta_persona_insight", "data_registry", "dcat_dataset_vec",
              "dcat_provenance", "dcat_dataset_attr", "active_meta_dataset",
              "meta_datagokr_file", "dataset_credentials"]
    for t in tables:
        cur.execute(f"SELECT count(*) FILTER (WHERE dataset_id !~ '^urn:'), count(*) FROM {t}")
        nonurn, total = cur.fetchone()
        if nonurn:
            fail("C-1", f"{t} — 구 slug {nonurn}행")
            bad(f"{t:<24} {nonurn:,}/{total:,}행이 구 slug")
        else:
            ok(f"{t:<24} {total:>7,}행 전부 URN")
    cur.execute(
        """SELECT count(*) FROM dcat_provenance p
             LEFT JOIN dcat_dataset d USING (dataset_id) WHERE d.dataset_id IS NULL"""
    )
    n = cur.fetchone()[0]
    (ok if n == 0 else bad)(f"dcat_provenance 끊어진 참조: {n}건 (FK가 없어 DB가 안 막아준다)")
    if n:
        fail("C-2", f"dcat_provenance 끊어진 참조 {n}건")

    # ── D. FK ON UPDATE ─────────────────────────────────────────────────────
    section("D. FK — dataset_id 참조가 전부 ON UPDATE CASCADE인가")
    cur.execute(
        """SELECT tc.table_name, rc.update_rule
             FROM information_schema.table_constraints tc
             JOIN information_schema.referential_constraints rc USING (constraint_name)
             JOIN information_schema.constraint_column_usage ccu USING (constraint_name)
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND ccu.table_name = 'dcat_dataset' AND ccu.column_name = 'dataset_id'"""
    )
    fks = cur.fetchall()
    noact = [t for t, u in fks if u != "CASCADE"]
    if noact:
        fail("D-1", f"ON UPDATE가 CASCADE가 아닌 FK: {noact}")
        bad(f"{len(fks)}건 중 CASCADE {len(fks) - len(noact)}건 — {noact}")
    else:
        ok(f"FK {len(fks)}건 전부 ON UPDATE CASCADE")

    # ── E. S3 경로 (레지스트리) ─────────────────────────────────────────────
    section("E. data_registry.s3_*_prefix — 코드가 만드는 경로와 같은가")
    cur.execute(
        """SELECT d.dataset_id, d.source_type, r.s3_raw_prefix, r.s3_jsonld_prefix
             FROM dcat_dataset d JOIN data_registry r USING (dataset_id) ORDER BY 1"""
    )
    nset = 0
    for did, st, raw, js in cur.fetchall():
        k = storage_key(did)
        want_raw, want_js = f"raw/{st}/{k}/", f"jsonld/{st}/{k}/"
        if raw is None and js is None:
            continue  # 아직 내보내기 전 — 정상
        nset += 1
        if raw != want_raw:
            fail("E-1", f"{did} — raw {raw!r} ≠ {want_raw!r}")
        if js != want_js:
            fail("E-1", f"{did} — jsonld {js!r} ≠ {want_js!r}")
        if (raw is None) != (js is None):
            fail("E-2", f"{did} — raw/jsonld 한쪽만 설정됨")
    cur.execute("SELECT count(*) FROM data_registry WHERE s3_raw_prefix = '' OR s3_jsonld_prefix = ''")
    nempty = cur.fetchone()[0]
    if nempty:
        fail("E-3", f"빈 문자열 {nempty}건 (NULL이어야 한다)")
    n1 = sum(1 for f in _fail if f.startswith("E-"))
    (ok if n1 == 0 else bad)(f"경로 설정된 {nset}건 검사, 위반 {n1}건 "
                             f"(미설정 {len(rows) - nset}건은 내보내기 전)")

    if not use_s3:
        conn.close()
        return report()

    # ── F. S3 실물 ──────────────────────────────────────────────────────────
    section("F. S3 실물 — 객체가 레지스트리 경로 아래 있는가")
    from src.storage.s3_client import get_s3_client
    from src.common import config
    s3 = get_s3_client()
    seen = {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=config.S3_BUCKET):
        for o in page.get("Contents", []):
            seen["/".join(o["Key"].split("/")[:3]) + "/"] = seen.get(
                "/".join(o["Key"].split("/")[:3]) + "/", 0) + 1
    cur.execute("""SELECT dataset_id, s3_raw_prefix, s3_jsonld_prefix FROM data_registry
                    WHERE s3_raw_prefix IS NOT NULL ORDER BY 1""")
    known = set()
    claims = cur.fetchall()
    for did, raw, js in claims:
        known.update([raw, js])
        print(f"  {did}")
        for pfx in (raw, js):
            n = seen.get(pfx, 0)
            print(f"     {pfx:<52} {n:>5,}개" + ("" if n else "   (비어 있음)"))
    orphan = {p: n for p, n in seen.items() if p not in known}
    if orphan:
        for p, n in sorted(orphan.items()):
            fail("F-1", f"레지스트리에 없는 경로에 객체 {n}개: {p}")
            bad(f"고아 경로: {p} ({n:,}개)")
    else:
        ok("레지스트리에 없는 경로의 객체 없음")

    # 반대 방향 — 레지스트리가 경로를 주장하는데 객체가 0개인 경우.
    # 규칙 위반은 아니지만(prefix는 '데이터가 갈 곳'이기도 하다) 내보내기를 한
    # 적이 없는 데이터셋은 NULL인 쪽과 표현이 갈린다. 둘 다 "아직 없음"인데
    # 11건은 NULL, 몇 건은 경로가 박혀 있으면 레지스트리만 보고는 구분이 안 된다.
    empty_claims = [(p, did) for did, raw, js in
                    [(d, r, j) for d, r, j in claims] for p in (raw, js)
                    if seen.get(p, 0) == 0]
    if empty_claims:
        for p, did in empty_claims:
            warn("F-2", f"{did} — 레지스트리가 {p} 를 가리키는데 객체 0개")
        print(f"  ⚠️  경로가 설정됐는데 객체가 없는 항목 {len(empty_claims)}건 "
              f"(내보내기를 한 적이 없음 — 아래 경고 참조)")
    else:
        ok("레지스트리 경로에 전부 객체가 있음")

    # ── G. JSON-LD ──────────────────────────────────────────────────────────
    section("G. JSON-LD — @id·adms:identifier가 DB와 일치하는가")
    ext_by_id = {r[0]: r[4] for r in rows}
    for page in s3.get_paginator("list_objects_v2").paginate(
            Bucket=config.S3_BUCKET, Prefix="jsonld/"):
        for o in sorted(page.get("Contents", []), key=lambda x: x["Key"]):
            doc = json.loads(s3.get_object(Bucket=config.S3_BUCKET, Key=o["Key"])["Body"].read())
            did = doc.get("@id")
            print(f"  {o['Key']}")
            if did not in ext_by_id:
                fail("G-1", f"{o['Key']} — @id {did!r}가 dcat_dataset에 없음")
                bad(f"     @id={did!r} — DB에 없음")
                continue
            if doc.get("dct:identifier") != did:
                fail("G-2", f"{o['Key']} — @id와 dct:identifier 불일치")
            got, want = doc.get("adms:identifier"), ext_by_id[did]
            if got != want:
                fail("G-3", f"{o['Key']} — adms:identifier {got} ≠ DB {want}")
                bad(f"     adms:identifier 불일치")
            else:
                print(f"     @id={did}")
                print(f"     adms:identifier={got}  ✅ DB와 일치")
            if "adms" not in doc.get("@context", {}):
                fail("G-4", f"{o['Key']} — @context에 adms 네임스페이스 없음")

    conn.close()
    return report()


def report() -> int:
    print(f"\n{'═' * 70}")
    if _warn:
        print(f"⚠️  경고 {len(_warn)}건")
        for w in _warn:
            print(f"   {w}")
    if _fail:
        print(f"❌ 위반 {len(_fail)}건")
        for f in _fail:
            print(f"   {f}")
        return 1
    print("✅ 모든 규칙 준수 — 위반 0건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
