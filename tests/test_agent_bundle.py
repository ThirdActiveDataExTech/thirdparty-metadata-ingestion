"""격리 환경 수집 — 파일 어댑터와 서명된 수집 번들 (A1 · 3차년도, 2026-11-11).

반입기는 **받는 것보다 거부하는 것이 중요하다.** 등록 안 된 에이전트, 변조, 재반입, 경로 장난,
데이터셋 바꿔치기는 반드시 거부돼야 한다. 키는 테스트 안에서 만들고 버린다.
"""

import json
import zipfile
from pathlib import Path

import pytest
import yaml

from src.agent import bundle as B
from src.collectors.adapters import file_source as F
from src.collectors.base import CollectorError
from src.packaging import manifest as M, signing


# ── 파일 어댑터 ─────────────────────────────────────────────────────────────

def _spec(tmp_path, **kw):
    spec = {"kind": "file", "source": "site", "path": "data/*.csv",
            "fields": {"id": "번호", "title": "제목"}, "id_field": "번호", **kw}
    p = tmp_path / "src.yaml"
    p.write_text(yaml.safe_dump(spec, allow_unicode=True), encoding="utf-8")
    return p


class TestFileCollector:
    def test_CSV를_이름순으로_읽고_정규화한다(self, tmp_path):
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "b.csv").write_text("번호,제목\n2,<b>둘</b>\n", encoding="utf-8")
        (tmp_path / "data" / "a.csv").write_text("번호,제목\n1,하나\n", encoding="utf-8-sig")
        c = F.adapter_from_file(str(_spec(tmp_path)))
        rows = [c.normalize(r) for r in c.fetch()]
        assert rows == [{"id": "1", "title": "하나"}, {"id": "2", "title": "둘"}]   # 태그도 벗긴다

    def test_JSONL과_JSON_배열(self, tmp_path):
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "x.jsonl").write_text('{"번호": 1}\n\n{"번호": 2}\n', encoding="utf-8")
        c = F.adapter_from_file(str(_spec(tmp_path, path="data/*.jsonl")))
        assert [c.item_id(c.normalize(r)) for r in c.fetch()] == ["1", "2"]
        (tmp_path / "data" / "y.json").write_text('{"result": {"list": [{"번호": 9}]}}', encoding="utf-8")
        c = F.adapter_from_file(str(_spec(tmp_path, path="data/*.json", items_path="result.list")))
        assert [r["번호"] for r in c.fetch()] == [9]

    def test_파일이_없거나_형식을_모르면_분명히_실패한다(self, tmp_path):
        with pytest.raises(CollectorError):
            list(F.adapter_from_file(str(_spec(tmp_path))).fetch())
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "z.txt").write_text("x", encoding="utf-8")
        with pytest.raises(CollectorError):
            list(F.adapter_from_file(str(_spec(tmp_path, path="data/*.txt"))).fetch())
        with pytest.raises(CollectorError):
            F.FileCollector({"source": "s", "path": "x", "format": "xml"})

    def test_깨진_JSONL은_몇_행인지_알린다(self, tmp_path):
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "x.jsonl").write_text('{"번호": 1}\n{깨짐\n', encoding="utf-8")
        with pytest.raises(CollectorError, match="2행"):
            list(F.adapter_from_file(str(_spec(tmp_path, path="data/*.jsonl"))).fetch())

    def test_파일_원천은_삭제를_판정하지_않는다(self, tmp_path):
        c = F.FileCollector({"source": "s", "path": "x"})
        assert c.detect_removed(["a", "b"], ["a"]) == []

    def test_종류를_모르면_거부한다(self, tmp_path):
        p = tmp_path / "s.yaml"
        p.write_text("kind: ftp\nsource: s\n", encoding="utf-8")
        with pytest.raises(CollectorError):
            F.adapter_from_file(str(p))


# ── 번들 ────────────────────────────────────────────────────────────────────

DS = "urn:test:site_dataset"


@pytest.fixture
def site(tmp_path, monkeypatch):
    """현장 파일 + 파이프라인 스펙 + 에이전트 키 + 플랫폼 신뢰 목록."""
    monkeypatch.setattr(M.config, "get_env", lambda n, d=None: None)
    monkeypatch.delenv(signing.PRIVATE_KEY_ENV, raising=False)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "a.csv").write_text("번호,제목,비고\n1,하나,x\n2,둘,y\n3,,z\n", encoding="utf-8")
    src = _spec(tmp_path)
    pipes = tmp_path / "pipelines"
    pipes.mkdir()
    (pipes / "site_pipe.yaml").write_text(yaml.safe_dump({
        "source_spec": str(src), "dataset_id": DS, "source_type": "site",
        "target": {"table": "meta_site", "columns": ["id", "title"], "conflict_key": "id"},
        "postprocess": ["embed"]}, allow_unicode=True), encoding="utf-8")
    from src.pipeline_engine import runner
    monkeypatch.setattr(runner, "PIPELINE_ROOT", pipes)

    agent_key = signing.Ed25519PrivateKey.generate()
    trusted = tmp_path / "agents"
    trusted.mkdir()
    (trusted / "site_a.pub.pem").write_bytes(signing.public_pem(agent_key.public_key()))
    monkeypatch.setenv(B.TRUSTED_DIR_ENV, str(trusted))

    out = tmp_path / "bundle.zip"
    man = B.collect_bundle(str(pipes / "site_pipe.yaml"), out, agent_key, agent_id="현장A")
    return {"tmp": tmp_path, "out": out, "man": man, "key": agent_key, "trusted": trusted, "pipes": pipes}


class FakeCur:
    def __init__(self, db):
        self.db = db
        self._r = []

    def execute(self, sql, params=None):
        self.db.sql.append((" ".join(sql.split()), params))
        if "bundle_sha256" in sql and sql.lstrip().startswith("SELECT"):
            self._r = [(1,)] if params[1] in self.db.seen else []
        elif sql.startswith("SELECT count(*)"):
            self._r = [(42,)]
        else:
            self._r = []

    def fetchone(self):
        return self._r[0] if self._r else None


class FakeDB:
    def __init__(self, seen=()):
        self.seen, self.sql, self.commits = set(seen), [], 0

    def cursor(self):
        return FakeCur(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


@pytest.fixture
def platform(monkeypatch):
    calls = {}
    db = FakeDB()
    import src.database.db as dbmod
    from src.database import dcat
    from src.pipeline_engine import runner, steps
    monkeypatch.setattr(dbmod, "get_conn", lambda: db)
    monkeypatch.setattr(steps, "store", lambda rows, ds, table, cols, key, defaults=None, dry_run=False:
                        calls.setdefault("store", (rows, ds, table, cols, dry_run)) and
                        {"attempted": len(rows), "stored": 0 if dry_run else len(rows)})
    monkeypatch.setattr(steps, "postprocess", lambda ds, st, acts, dry_run=False:
                        calls.setdefault("post", (ds, list(acts), dry_run)) and {})
    monkeypatch.setattr(runner, "_check_drift", lambda ds, raws, adapter, dry_run:
                        calls.setdefault("drift", (ds, len(raws))) and {"status": "ok"})
    monkeypatch.setattr(dcat, "update_data_registry", lambda ds, **kw: calls.setdefault("registry", (ds, kw)))
    return db, calls


def _rewrite(src, out, mutate):
    with zipfile.ZipFile(src) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    mutate(parts)
    with zipfile.ZipFile(out, "w") as z:
        for n, b in parts.items():
            z.writestr(n, b)
    return out


class TestCollect:
    def test_번들은_대상_컬럼만_담고_원본_표본과_bundle_절이_있다(self, site):
        z = zipfile.ZipFile(site["out"])
        rows = [json.loads(x) for x in z.read("data/rows.jsonl").decode().splitlines()]
        assert rows == [{"id": "1", "title": "하나"}, {"id": "2", "title": "둘"}, {"id": "3", "title": ""}]
        b = site["man"]["bundle"]
        assert b["kind"] == B.BUNDLE_KIND and b["pipeline"] == "site_pipe" and b["dataset_id"] == DS
        assert b["raw_count"] == 3 and b["row_count"] == 3 and b["adapter_kind"] == "file"
        assert site["man"]["signer"]["algorithms"] == ["ed25519"]

    def test_에이전트_키가_없으면_만들지_않는다(self, monkeypatch):
        monkeypatch.delenv(B.AGENT_KEY_ENV, raising=False)
        with pytest.raises(B.BundleError):
            B.agent_key_from_env()


class TestIngest:
    def test_등록된_에이전트_번들을_플랫폼_스펙대로_들인다(self, site, platform):
        db, calls = platform
        r = B.ingest_bundle(site["out"])
        assert r["signer"] == "site_a.pub.pem" and r["rows"] == 3 and r["item_count"] == 42
        rows, ds, table, cols, dry = calls["store"]
        assert (ds, table, cols, dry) == (DS, "meta_site", ["id", "title"], False)
        assert calls["drift"] == (DS, 3) and calls["post"] == (DS, ["embed"], False)
        ins = [p for q, p in db.sql if q.startswith("INSERT INTO dcat_provenance")]
        assert len(ins) == 1 and ins[0][2] == "agent:site_a.pub.pem"
        assert json.loads(ins[0][5])["agent_id"] == "현장A"
        assert calls["registry"][0] == DS

    def test_dry_run은_쓰지_않는다(self, site, platform):
        db, calls = platform
        r = B.ingest_bundle(site["out"], dry_run=True)
        assert r["dry_run"] and calls["store"][4] is True and calls["post"][2] is True
        assert not [q for q, _ in db.sql if q.startswith("INSERT")] and db.commits == 0

    def test_등록되지_않은_에이전트는_403(self, site, platform):
        for p in site["trusted"].glob("*.pem"):
            p.unlink()
        (site["trusted"] / "other.pub.pem").write_bytes(
            signing.public_pem(signing.Ed25519PrivateKey.generate().public_key()))
        with pytest.raises(B.BundleError) as e:
            B.ingest_bundle(site["out"])
        assert e.value.code == 403

    def test_신뢰_목록이_비면_403(self, site, platform):
        for p in site["trusted"].glob("*.pem"):
            p.unlink()
        with pytest.raises(B.BundleError) as e:
            B.ingest_bundle(site["out"])
        assert e.value.code == 403

    def test_행을_바꾸면_거부한다(self, site, platform):
        bad = _rewrite(site["out"], site["tmp"] / "bad.zip",
                       lambda p: p.__setitem__("data/rows.jsonl", p["data/rows.jsonl"].replace("하나".encode(), "셋".encode())))
        with pytest.raises(B.BundleError, match="서명과 맞지 않습니다"):
            B.ingest_bundle(bad)

    def test_같은_번들은_두_번_들이지_않는다(self, site, platform):
        db, _ = platform
        db.seen.add(M.manifest_sha256(site["man"]))
        with pytest.raises(B.BundleError) as e:
            B.ingest_bundle(site["out"])
        assert e.value.code == 409

    def _resign(self, site, mutate_bundle, name):
        """등록된 에이전트가 직접 서명한(=서명은 유효한) 비정상 번들."""
        def m(p):
            man = json.loads(p[M.MANIFEST_NAME])
            mutate_bundle(man)
            p[M.MANIFEST_NAME] = json.dumps(man).encode()
            p[signing.SIGNATURE_NAME] = signing.sign(M.canonical_bytes(man), site["key"]).encode()
        return _rewrite(site["out"], site["tmp"] / name, m)

    @pytest.mark.parametrize("bad_name", ["../../etc/passwd", "/abs/path", "Site-Pipe", ""])
    def test_파이프라인_이름에_경로를_넣으면_거부한다(self, site, platform, bad_name):
        p = self._resign(site, lambda m: m["bundle"].__setitem__("pipeline", bad_name), "n.zip")
        with pytest.raises(B.BundleError, match="이름 형식"):
            B.ingest_bundle(p)

    def test_플랫폼에_없는_파이프라인은_거부한다(self, site, platform):
        p = self._resign(site, lambda m: m["bundle"].__setitem__("pipeline", "nope"), "x.zip")
        with pytest.raises(B.BundleError, match="없습니다"):
            B.ingest_bundle(p)

    def test_데이터셋을_바꿔치기하면_거부한다(self, site, platform):
        def m(man):
            man["bundle"]["dataset_id"] = "urn:other"
            man["dataset_id"] = "urn:other"
        with pytest.raises(B.BundleError, match="데이터셋"):
            B.ingest_bundle(self._resign(site, m, "d.zip"))

    def test_번들이_아닌_패키지는_거부한다(self, site, platform):
        with pytest.raises(B.BundleError, match="수집 번들이 아닙니다"):
            B.ingest_bundle(self._resign(site, lambda m: m.pop("bundle"), "nb.zip"))

    def test_행_수가_기록과_다르면_거부한다(self, site, platform):
        with pytest.raises(B.BundleError, match="행 수"):
            B.ingest_bundle(self._resign(site, lambda m: m["bundle"].__setitem__("row_count", 99), "rc.zip"))


def test_API는_관리자만(monkeypatch):
    from fastapi.testclient import TestClient
    from src.api.main import app
    r = TestClient(app).post("/v1/console/agent-bundles", files={"file": ("b.zip", b"x")})
    assert r.status_code == 401
