"""데이터 패키징 (C5) — 신뢰의 사슬이 실제로 끊기는지.

검증기는 **통과시키는 것보다 거부하는 것이 중요하다.** 변조를 못 잡는 검증기는
통과 도장만 찍어 주므로 없느니만 못하다. 그래서 여기 테스트의 대부분이
"이건 반드시 거부돼야 한다"이다.
"""

import json
import zipfile
from pathlib import Path

import pytest

from src.packaging import builder, manifest as M, verify as V

KEY = "테스트-전용-키"


@pytest.fixture
def pkg(tmp_path, monkeypatch):
    """서명된 패키지 하나를 만들어 준다."""
    monkeypatch.setattr(M.config, "get_env", lambda n, d=None: KEY)
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "a.json").write_text('{"t":"HBM"}', encoding="utf-8")
    (src / "sub" / "b.txt").write_text("두 번째", encoding="utf-8")
    out = tmp_path / "p.zip"
    man = builder.build_package("urn:test:ds", src, out,
                                source={"title": "테스트"}, features={"item_count": 1})
    return {"path": out, "manifest": man, "tmp": tmp_path}


def tamper(pkg, name, mutate):
    """패키지를 한 군데 바꿔 새 파일로 만든다."""
    out = pkg["tmp"] / f"{name}.zip"
    with zipfile.ZipFile(pkg["path"]) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    mutate(parts)
    with zipfile.ZipFile(out, "w") as z:
        for n, b in parts.items():
            z.writestr(n, b)
    return out


class TestCanonical:
    def test_키_순서가_달라도_같은_바이트(self):
        # 직렬화가 흔들리면 같은 내용인데 서명이 깨진다
        a = {"b": 1, "a": 2}
        b = {"a": 2, "b": 1}
        assert M.canonical_bytes(a) == M.canonical_bytes(b)

    def test_한글이_이스케이프되지_않는다(self):
        assert "한글".encode("utf-8") in M.canonical_bytes({"k": "한글"})


class TestSigning:
    def test_키가_없으면_분명히_실패한다(self, monkeypatch):
        monkeypatch.setattr(M.config, "get_env", lambda n, d=None: None)
        with pytest.raises(M.ManifestError) as e:
            M.sign({"a": 1})
        assert M.SIGNING_KEY_ENV in str(e.value)

    def test_같은_내용은_같은_서명(self):
        m = {"a": 1, "b": [1, 2]}
        assert M.sign(m, KEY) == M.sign(dict(reversed(list(m.items()))), KEY)

    def test_내용이_바뀌면_서명이_바뀐다(self):
        assert M.sign({"a": 1}, KEY) != M.sign({"a": 2}, KEY)

    def test_키가_다르면_검증_실패(self):
        s = M.sign({"a": 1}, KEY)
        assert M.verify_signature({"a": 1}, s, KEY) is True
        assert M.verify_signature({"a": 1}, s, "다른키") is False

    def test_서명은_manifest_안에_들어가지_않는다(self, pkg):
        # 들어가면 "서명을 포함한 상태"를 서명해야 하는 순환이 생긴다
        assert "signature" not in pkg["manifest"]
        assert "sig" not in pkg["manifest"]


class TestBuild:
    def test_빈_패키지는_만들지_않는다(self, tmp_path, monkeypatch):
        monkeypatch.setattr(M.config, "get_env", lambda n, d=None: KEY)
        (tmp_path / "empty").mkdir()
        with pytest.raises(M.ManifestError):
            builder.build_package("urn:test:x", tmp_path / "empty", tmp_path / "o.zip")

    def test_없는_디렉터리는_거부한다(self, tmp_path, monkeypatch):
        monkeypatch.setattr(M.config, "get_env", lambda n, d=None: KEY)
        with pytest.raises(M.ManifestError):
            builder.build_package("urn:test:x", tmp_path / "없음", tmp_path / "o.zip")

    def test_경로는_패키지_안_상대경로다(self, pkg):
        # 절대 경로를 넣으면 만든 사람의 디렉터리 구조가 새어 나간다
        for f in pkg["manifest"]["files"]:
            assert f["path"].startswith("data/")
            assert not Path(f["path"]).is_absolute()

    def test_하위_디렉터리를_보존한다(self, pkg):
        paths = {f["path"] for f in pkg["manifest"]["files"]}
        assert "data/sub/b.txt" in paths

    def test_출처와_통계를_담는다(self, pkg):
        # manifest만으로 출처 추적이 가능해야 한다(완료 기준)
        assert pkg["manifest"]["source"]["title"] == "테스트"
        assert pkg["manifest"]["features"]["item_count"] == 1


class TestVerifyAccepts:
    def test_손대지_않은_패키지는_통과(self, pkg):
        assert V.verify_package(pkg["path"], key=KEY).ok

    def test_DB_없이_검증된다(self, pkg, monkeypatch):
        # 완료 기준: "타 환경에서 체크섬·서명 검증 통과"
        import src.database.db as db

        def _boom(*a, **k):
            raise AssertionError("검증이 DB를 건드렸다")

        monkeypatch.setattr(db, "get_conn", _boom)
        assert V.verify_package(pkg["path"], key=KEY).ok


class TestVerifyRejects:
    def test_데이터_파일_변조(self, pkg):
        p = tamper(pkg, "t1", lambda d: d.__setitem__(
            "data/a.json", d["data/a.json"].replace(b"HBM", b"XXX")))
        r = V.verify_package(p, key=KEY)
        assert not r.ok and any("체크섬" in x for x in r.problems)

    def test_manifest_변조는_서명에서_걸린다(self, pkg):
        # 체크섬을 고쳐 변조를 숨기려는 시도
        def f(d):
            m = json.loads(d["manifest.json"])
            m["files"][0]["sha256"] = "0" * 64
            d["manifest.json"] = json.dumps(m, sort_keys=True).encode()

        r = V.verify_package(tamper(pkg, "t2", f), key=KEY)
        assert not r.ok and any("서명" in x for x in r.problems)

    def test_manifest에_없는_파일이_끼어들면_거부(self, pkg):
        p = tamper(pkg, "t3", lambda d: d.__setitem__("data/x.txt", b"sneak"))
        r = V.verify_package(p, key=KEY)
        assert not r.ok and any("manifest에 없는" in x for x in r.problems)

    def test_파일이_빠지면_거부(self, pkg):
        p = tamper(pkg, "t4", lambda d: d.pop("data/sub/b.txt"))
        r = V.verify_package(p, key=KEY)
        assert not r.ok and any("패키지에 없는" in x for x in r.problems)

    def test_서명_파일이_없으면_거부(self, pkg):
        p = tamper(pkg, "t5", lambda d: d.pop(M.SIGNATURE_NAME))
        assert not V.verify_package(p, key=KEY).ok

    def test_모르는_형식은_거부한다(self, pkg):
        # 조용히 통과시키는 대신 분명히 거부해야 한다
        def f(d):
            m = json.loads(d["manifest.json"])
            m["manifest_version"] = "99.0"
            d["manifest.json"] = json.dumps(m, sort_keys=True).encode()

        r = V.verify_package(tamper(pkg, "t6", f), key=KEY)
        assert not r.ok and any("모르는 manifest 형식" in x for x in r.problems)

    def test_틀린_키는_거부한다(self, pkg):
        assert not V.verify_package(pkg["path"], key="틀린키").ok

    def test_없는_파일은_거부한다(self, tmp_path):
        assert not V.verify_package(tmp_path / "없음.zip", key=KEY).ok
