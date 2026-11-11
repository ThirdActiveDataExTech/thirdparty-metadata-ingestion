"""신뢰 패키지 1.1 — 공개키 서명·출처 확인·손상 복원·암호화·데이터 점검 (2026-11-11).

여기 키는 전부 테스트 안에서 만들고 버린다(운영 키 아님).
"""

import io
import json
import os
import zipfile

import pytest
from fastapi.testclient import TestClient

import src.api.main  # noqa: F401 — 설정 읽기를 가짜로 바꾸는 픽스처보다 먼저 API를 올려 둔다
from src.packaging import builder, envelope, manifest as M, quality, recovery, signing, verify as V


@pytest.fixture
def no_hmac(monkeypatch):
    monkeypatch.setattr(M.config, "get_env", lambda n, d=None: None)
    monkeypatch.delenv(signing.PRIVATE_KEY_ENV, raising=False)


def _key():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    return Ed25519PrivateKey.generate()


def _src(tmp_path, big=0):
    src = tmp_path / "src"
    src.mkdir()
    (src / "metadata.jsonld").write_text('{"@id":"urn:test:ds"}', encoding="utf-8")
    (src / "items.csv").write_text("id,title\n1,가\n2,나\n2,나\n", encoding="utf-8")
    if big:
        (src / "big.bin").write_bytes(os.urandom(big))
    return src


@pytest.fixture
def signed(tmp_path, no_hmac):
    key = _key()
    out = tmp_path / "p.zip"
    man = builder.build_package("urn:test:ds", _src(tmp_path, big=recovery.BLOCK_SIZE * 3 + 100), out,
                                ed25519_key=key, context={"lineage": {"collection_runs": [{"status": "success"}]},
                                                          "reference": {"publisher": "테스트기관"}},
                                expected_rows={"items.csv": 3})
    return {"path": out, "key": key, "man": man, "tmp": tmp_path,
            "pub": signing.public_pem(key.public_key())}


def _rewrite(path, out, mutate):
    with zipfile.ZipFile(path) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    mutate(parts)
    with zipfile.ZipFile(out, "w") as z:
        for n, b in parts.items():
            z.writestr(n, b)
    return out


class TestPublicKeySignature:
    def test_공개키_서명만으로_만들고_검증한다(self, signed):
        names = zipfile.ZipFile(signed["path"]).namelist()
        assert signing.SIGNATURE_NAME in names and M.SIGNATURE_NAME not in names
        r = V.verify_package(signed["path"])
        assert r.ok and r.signatures == {"ed25519": "ok"}
        assert r.signer_trusted is False          # 패키지에 든 키로만 확인했다

    def test_공식_공개키를_주면_출처까지_확인한다(self, signed):
        r = V.verify_package(signed["path"], pubkey_pem=signed["pub"])
        assert r.ok and r.signer_trusted
        assert r.signer_fingerprint == signed["man"]["signer"]["ed25519_fingerprint"]

    def test_다른_공개키면_거부한다(self, signed):
        r = V.verify_package(signed["path"], pubkey_pem=signing.public_pem(_key().public_key()))
        assert not r.ok and r.signatures["ed25519"] == "fail"

    def test_manifest_변조는_서명에서_걸린다(self, signed):
        def m(p):
            man = json.loads(p[M.MANIFEST_NAME])
            man["source"]["title"] = "바꿈"
            p[M.MANIFEST_NAME] = json.dumps(man).encode()
        r = V.verify_package(_rewrite(signed["path"], signed["tmp"] / "t.zip", m))
        assert not r.ok and r.signatures["ed25519"] == "fail"

    def test_키와_서명을_통째로_바꿔치기하면_공식_키로만_잡힌다(self, signed):
        """위조자가 자기 키로 manifest를 다시 서명하고 공개키·지문까지 바꿔 넣은 경우."""
        evil = _key()

        def m(p):
            man = json.loads(p[M.MANIFEST_NAME])
            man["source"]["title"] = "위조"
            man["signer"]["ed25519_fingerprint"] = signing.fingerprint(evil.public_key())
            p[M.MANIFEST_NAME] = json.dumps(man).encode()
            p[signing.SIGNATURE_NAME] = signing.sign(M.canonical_bytes(man), evil).encode()
            p[signing.PUBLIC_KEY_NAME] = signing.public_pem(evil.public_key())
        forged = _rewrite(signed["path"], signed["tmp"] / "f.zip", m)
        loose = V.verify_package(forged)
        assert loose.ok and not loose.signer_trusted      # 무결성만 — 출처는 보장 못 한다
        strict = V.verify_package(forged, pubkey_pem=signed["pub"])
        assert not strict.ok

    def test_패키지_공개키와_manifest_지문이_다르면_거부한다(self, signed):
        def m(p):
            p[signing.PUBLIC_KEY_NAME] = signing.public_pem(_key().public_key())
        r = V.verify_package(_rewrite(signed["path"], signed["tmp"] / "k.zip", m))
        assert not r.ok

    def test_HMAC과_함께_서명하면_키_없는_수신자도_공개키로_통과한다(self, tmp_path, monkeypatch):
        monkeypatch.setattr(M.config, "get_env", lambda n, d=None: "공유키")
        out = tmp_path / "both.zip"
        builder.build_package("urn:test:ds", _src(tmp_path), out, ed25519_key=_key())
        monkeypatch.setattr(M.config, "get_env", lambda n, d=None: None)
        r = V.verify_package(out)
        assert r.ok and r.signatures == {"ed25519": "ok", "hmac-sha256": "unchecked"}

    def test_HMAC만_있고_키가_없으면_통과시키지_않는다(self, tmp_path, monkeypatch):
        monkeypatch.setattr(M.config, "get_env", lambda n, d=None: "공유키")
        monkeypatch.delenv(signing.PRIVATE_KEY_ENV, raising=False)
        out = tmp_path / "h.zip"
        builder.build_package("urn:test:ds", _src(tmp_path), out)
        monkeypatch.setattr(M.config, "get_env", lambda n, d=None: None)
        r = V.verify_package(out)
        assert not r.ok and r.signatures == {"hmac-sha256": "unchecked"}

    def test_서명_키가_하나도_없으면_만들지_않는다(self, tmp_path, no_hmac):
        with pytest.raises(M.ManifestError):
            builder.build_package("urn:test:ds", _src(tmp_path), tmp_path / "x.zip")

    def test_환경변수의_비밀키를_쓴다(self, tmp_path, no_hmac, monkeypatch):
        priv, pub = signing.generate()
        monkeypatch.setenv(signing.PRIVATE_KEY_ENV, priv.decode().replace("\n", "\\n"))
        out = tmp_path / "e.zip"
        builder.build_package("urn:test:ds", _src(tmp_path), out)
        assert V.verify_package(out, pubkey_pem=pub).signer_trusted


class TestRecovery:
    def test_블록_하나가_깨지면_찾아서_복원한다(self, signed):
        def m(p):
            b = bytearray(p["data/big.bin"])
            b[recovery.BLOCK_SIZE + 5] ^= 0xFF
            p["data/big.bin"] = bytes(b)
        bad = _rewrite(signed["path"], signed["tmp"] / "bad.zip", m)
        r = V.verify_package(bad)
        assert not r.ok and r.repairable == ["data/big.bin"] and not r.unrepairable
        fixed = V.repair_package(bad, signed["tmp"] / "fixed.zip", pubkey_pem=signed["pub"])
        assert fixed.ok and fixed.signer_trusted

    def test_마지막_짧은_블록도_복원한다(self, signed):
        def m(p):
            b = bytearray(p["data/big.bin"])
            b[-1] ^= 0x01
            p["data/big.bin"] = bytes(b)
        bad = _rewrite(signed["path"], signed["tmp"] / "tail.zip", m)
        assert V.repair_package(bad, signed["tmp"] / "tail_fixed.zip").ok

    def test_작은_파일도_복원한다(self, signed):
        def m(p):
            p["data/items.csv"] = p["data/items.csv"].replace("가".encode(), "다".encode())
        bad = _rewrite(signed["path"], signed["tmp"] / "s.zip", m)
        assert V.verify_package(bad).repairable == ["data/items.csv"]
        assert V.repair_package(bad, signed["tmp"] / "s_fixed.zip").ok

    def test_한_묶음에서_두_블록이_깨지면_복원하지_않는다(self, signed):
        def m(p):
            b = bytearray(p["data/big.bin"])
            b[5] ^= 0xFF
            b[recovery.BLOCK_SIZE + 5] ^= 0xFF
            p["data/big.bin"] = bytes(b)
        bad = _rewrite(signed["path"], signed["tmp"] / "two.zip", m)
        r = V.verify_package(bad)
        assert r.unrepairable == ["data/big.bin"]
        with pytest.raises(recovery.RecoveryError):
            V.repair_package(bad, signed["tmp"] / "no.zip")

    def test_길이가_바뀌면_복원하지_않는다(self, signed):
        def m(p):
            p["data/big.bin"] = p["data/big.bin"][:-10]
        r = V.verify_package(_rewrite(signed["path"], signed["tmp"] / "short.zip", m))
        assert r.unrepairable == ["data/big.bin"]

    def test_패리티_변조도_잡는다(self, signed):
        ppath = signed["man"]["recovery"]["files"]["data/big.bin"]["parity"]

        def m(p):
            b = bytearray(p[ppath])
            b[0] ^= 0xFF
            p[ppath] = bytes(b)
        r = V.verify_package(_rewrite(signed["path"], signed["tmp"] / "par.zip", m))
        assert not r.ok and any("복원 정보 체크섬" in x for x in r.problems)

    def test_서명이_틀린_패키지는_복원하지_않는다(self, signed):
        def m(p):
            p[signing.SIGNATURE_NAME] = signing.sign(b"x", _key()).encode()
        with pytest.raises(recovery.RecoveryError):
            V.repair_package(_rewrite(signed["path"], signed["tmp"] / "sig.zip", m), signed["tmp"] / "o.zip")

    def test_복원_정보_없이도_만들_수_있다(self, tmp_path, no_hmac):
        out = tmp_path / "nr.zip"
        man = builder.build_package("urn:test:ds", _src(tmp_path), out, ed25519_key=_key(), with_recovery=False)
        assert "recovery" not in man and V.verify_package(out).ok


class TestEnvelope:
    def test_암호화하고_풀면_원래_패키지다(self, signed):
        enc, dec = signed["tmp"] / "p.zip.enc", signed["tmp"] / "p2.zip"
        envelope.encrypt_file(signed["path"], enc, "비밀번호-123")
        assert b"manifest.json" not in enc.read_bytes()       # 내용이 드러나지 않는다
        envelope.decrypt_file(enc, dec, "비밀번호-123")
        assert dec.read_bytes() == signed["path"].read_bytes()
        assert V.verify_package(dec).ok

    def test_여러_청크도_순서대로_푼다(self):
        data = os.urandom(10_000)
        buf = io.BytesIO()
        envelope.encrypt_stream(io.BytesIO(data), buf, "pw", chunk=1024, log_n=10)
        out = io.BytesIO()
        envelope.decrypt_stream(io.BytesIO(buf.getvalue()), out, "pw")
        assert out.getvalue() == data

    @pytest.mark.parametrize("damage", ["wrong", "flip", "truncate", "drop_last"])
    def test_틀린_비밀번호_변조_절단은_거부한다(self, damage, tmp_path):
        data = os.urandom(5000)
        buf = io.BytesIO()
        envelope.encrypt_stream(io.BytesIO(data), buf, "pw", chunk=1024, log_n=10)
        raw = bytearray(buf.getvalue())
        pw = "pw"
        if damage == "wrong":
            pw = "pX"
        elif damage == "flip":
            raw[100] ^= 1
        elif damage == "truncate":
            raw = raw[:-7]
        elif damage == "drop_last":
            raw = raw[:-(5000 - 4 * 1024 + 16)]          # 마지막 청크를 통째로 뺀다
        with pytest.raises(envelope.EnvelopeError):
            envelope.decrypt_stream(io.BytesIO(bytes(raw)), io.BytesIO(), pw)

    def test_실패하면_결과_파일을_남기지_않는다(self, signed):
        enc, dec = signed["tmp"] / "q.zip.enc", signed["tmp"] / "q.zip"
        envelope.encrypt_file(signed["path"], enc, "pw")
        with pytest.raises(envelope.EnvelopeError):
            envelope.decrypt_file(enc, dec, "틀림")
        assert not dec.exists() and not (signed["tmp"] / "q.zip.part").exists()


class TestManifest11:
    def test_이력_레퍼런스_점검이_manifest에_있다(self, signed):
        man = signed["man"]
        assert man["manifest_version"] == "1.1"
        assert man["lineage"]["collection_runs"][0]["status"] == "success"
        assert man["reference"]["publisher"] == "테스트기관"
        assert man["signer"]["algorithms"] == ["ed25519"]

    def test_점검은_중복_행과_등록_건수를_본다(self, signed):
        q = signed["man"]["quality"]
        csv_p = q["files"]["data/items.csv"]
        assert csv_p["rows"] == 3 and csv_p["duplicate_rows"] == 1
        check = next(c for c in q["checks"] if c["name"] == "등록 건수와 행 수 일치")
        assert check["passed"] is True

    def test_점검에는_값을_담지_않는다(self, signed):
        assert "가" not in json.dumps(signed["man"]["quality"], ensure_ascii=False)

    def test_등록_건수와_다르면_실패로_적는다(self, tmp_path):
        src = _src(tmp_path)
        q = quality.profile(src, "data", {"items.csv": 10})
        assert q["failed"] == 1

    def test_깨진_JSON은_해석_실패로_적는다(self, tmp_path):
        (tmp_path / "a.json").write_text("{깨짐", encoding="utf-8")
        q = quality.profile(tmp_path, "data")
        assert q["files"]["data/a.json"]["parse_ok"] is False and q["failed"] == 1

    def test_1_0_패키지도_검증한다(self, tmp_path, monkeypatch):
        monkeypatch.setattr(M.config, "get_env", lambda n, d=None: "공유키")
        monkeypatch.delenv(signing.PRIVATE_KEY_ENV, raising=False)
        out = tmp_path / "old.zip"
        builder.build_package("urn:test:ds", _src(tmp_path), out, with_recovery=False)

        def m(p):
            man = json.loads(p[M.MANIFEST_NAME])
            man["manifest_version"] = "1.0"
            for k in M.EXTRA_SECTIONS:
                man.pop(k, None)
            p[M.MANIFEST_NAME] = json.dumps(man).encode()
            p[M.SIGNATURE_NAME] = M.sign(man, "공유키").encode()
        assert V.verify_package(_rewrite(out, tmp_path / "old2.zip", m)).ok


class TestApi:
    def test_공개키_API는_설정이_없으면_404(self, monkeypatch):
        from src.api.main import app
        monkeypatch.delenv(signing.PRIVATE_KEY_ENV, raising=False)
        assert TestClient(app).get("/v1/packaging/public-key").status_code == 404

    def test_공개키_API는_지문과_공개키만_준다(self, monkeypatch):
        from src.api.main import app
        priv, pub = signing.generate()
        monkeypatch.setenv(signing.PRIVATE_KEY_ENV, priv.decode())
        body = TestClient(app).get("/v1/packaging/public-key").json()
        assert body["public_key_pem"] == pub.decode()
        assert "PRIVATE" not in json.dumps(body)
        assert body["fingerprint"] == signing.fingerprint(signing.load_public_key(pub))


def test_keygen은_비밀키를_600으로_쓰고_덮어쓰지_않는다(tmp_path, monkeypatch, capsys):
    import sys
    from scripts import package_dataset as P
    monkeypatch.setattr(sys, "argv", ["x", "keygen", "--out", str(tmp_path)])
    assert P.main() == 0
    priv = tmp_path / "package_signing_ed25519.pem"
    assert oct(priv.stat().st_mode & 0o777) == "0o600"
    assert P.main() == 1                                  # 이미 있으면 거부


def test_zip이_아니면_안내하고_죽지_않는다(tmp_path):
    p = tmp_path / "x.zip"
    p.write_bytes(b"not a zip")
    r = V.verify_package(p)
    assert not r.ok and "zip 형식이 아니다" in r.problems[0]


class TestDiff:
    def _pkg(self, tmp_path, name, rows, key, runs, extra_file=False):
        src = tmp_path / f"src_{name}"
        src.mkdir()
        (src / "items.csv").write_text("id,title\n" + "".join(f"{i},t{i}\n" for i in range(rows)), encoding="utf-8")
        (src / "metadata.jsonld").write_text('{"@id":"urn:test:ds"}', encoding="utf-8")
        if extra_file:
            (src / "notes.txt").write_text("새 파일", encoding="utf-8")
        out = tmp_path / f"{name}.zip"
        builder.build_package("urn:test:ds", src, out, ed25519_key=key, version=name,
                              context={"lineage": {"collection_runs": runs}, "reference": {"license": "CC-BY"}},
                              expected_rows={"items.csv": rows})
        return out

    def test_버전_사이_변경을_짚는다(self, tmp_path, no_hmac):
        from src.packaging import diff as D
        k = _key()
        r1 = [{"started_at": "2026-11-01", "agent": "a", "status": "success"}]
        r2 = r1 + [{"started_at": "2026-11-10", "agent": "a", "status": "success"}]
        old = self._pkg(tmp_path, "v1", 3, k, r1)
        new = self._pkg(tmp_path, "v2", 5, k, r2, extra_file=True)
        d = D.diff_packages(old, new, pubkey_pem=signing.public_pem(k.public_key()))
        assert d["files"]["added"] == ["data/notes.txt"]
        assert [c["path"] for c in d["files"]["changed"]] == ["data/items.csv"]
        assert d["files"]["unchanged"] == 1
        assert d["tables"][0]["rows_before"] == 3 and d["tables"][0]["rows_after"] == 5
        assert len(d["new_collection_runs"]) == 1 and not d["identical_content"]

    def test_검증_안_되는_패키지는_비교하지_않는다(self, tmp_path, no_hmac):
        from src.packaging import diff as D
        old = self._pkg(tmp_path, "v1", 3, _key(), [])
        new = self._pkg(tmp_path, "v2", 3, _key(), [])
        with pytest.raises(D.DiffError):
            D.diff_packages(old, new, pubkey_pem=signing.public_pem(_key().public_key()))

    def test_다른_데이터셋은_비교하지_않는다(self):
        from src.packaging import diff as D
        base = {"dataset_id": "a", "version": "1", "created_at": "x", "files": []}
        with pytest.raises(D.DiffError):
            D.diff_manifests(base, dict(base, dataset_id="b"))


class TestVerifyApi:
    def _client(self, monkeypatch, priv=None):
        from fastapi.testclient import TestClient
        from src.api import auth
        from src.api.main import app
        if priv:
            monkeypatch.setenv(signing.PRIVATE_KEY_ENV, priv.decode())
        else:
            monkeypatch.delenv(signing.PRIVATE_KEY_ENV, raising=False)
        app.dependency_overrides[auth.current_user] = lambda: auth.User(id="u", name="u", role="user", org="A", org_name="기관 A")
        return TestClient(app), app, auth

    def test_공식_키로_만든_패키지는_출처까지_통과(self, tmp_path, no_hmac, monkeypatch):
        priv, _ = signing.generate()
        key = signing.load_private_key(priv.decode())
        out = tmp_path / "p.zip"
        builder.build_package("urn:test:ds", _src(tmp_path), out, ed25519_key=key)
        c, app, auth = self._client(monkeypatch, priv)
        try:
            r = c.post("/v1/packaging/verify", files={"file": ("p.zip", out.read_bytes(), "application/zip")}).json()
        finally:
            app.dependency_overrides.pop(auth.current_user, None)
        assert r["ok"] and r["signer_trusted"] and r["manifest"]["dataset_id"] == "urn:test:ds"

    def test_다른_키로_만든_패키지는_출처_불일치(self, tmp_path, no_hmac, monkeypatch):
        priv, _ = signing.generate()
        out = tmp_path / "p.zip"
        builder.build_package("urn:test:ds", _src(tmp_path), out, ed25519_key=_key())
        c, app, auth = self._client(monkeypatch, priv)
        try:
            r = c.post("/v1/packaging/verify", files={"file": ("p.zip", out.read_bytes(), "application/zip")}).json()
        finally:
            app.dependency_overrides.pop(auth.current_user, None)
        assert not r["ok"] and r["signatures"]["ed25519"] == "fail"

    def test_zip이_아니면_안내(self, monkeypatch):
        c, app, auth = self._client(monkeypatch)
        try:
            r = c.post("/v1/packaging/verify", files={"file": ("x.zip.enc", b"MPKGENC1xxxx", "application/octet-stream")}).json()
        finally:
            app.dependency_overrides.pop(auth.current_user, None)
        assert not r["ok"] and "decrypt" in r["problems"][0] and r["server_key_configured"] is False

    def test_로그인이_필요하다(self):
        from fastapi.testclient import TestClient
        from src.api.main import app
        assert TestClient(app).post("/v1/packaging/verify", files={"file": ("p.zip", b"x")}).status_code == 401
