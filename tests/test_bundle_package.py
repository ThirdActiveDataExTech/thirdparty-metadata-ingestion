"""묶음 신뢰 패키지·아이템 CSV 추출 (C5, 2026-11-11)."""

import io
import json
import zipfile

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.api import manage, usage
from src.api.main import app
from src.packaging import signing, verify as V


class Cur:
    description = [("id",), ("title",)]

    def __init__(self):
        self._r = []

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if s.startswith("SELECT title, publisher, license, source_type"):
            self._r = [(f"제목 {params[0]}", "기관", "CC-BY", "news")]
        elif "item_count FROM data_registry" in s:
            self._r = [(2,)]
        elif "pg_meta_table" in s:
            self._r = [("meta_news",)] if "nometa" not in params[0] else []
        elif s.startswith("SELECT * FROM meta_news"):
            self._r = [(1, "가"), (2, None)]
        else:
            self._r = []

    def fetchone(self):
        return self._r[0] if self._r else None

    def fetchall(self):
        return self._r


@pytest.fixture
def env(monkeypatch):
    priv, pub = signing.generate()
    monkeypatch.setenv(signing.PRIVATE_KEY_ENV, priv.decode())
    monkeypatch.setattr(manage.config, "get_env", lambda n, d=None: None)
    monkeypatch.setattr(manage, "get_conn", lambda: type("C", (), {"cursor": lambda self: Cur()})())
    monkeypatch.setattr(manage, "ensure_visible", lambda cur, ds, user: None)
    import src.storage.jsonld_export as je
    monkeypatch.setattr(je, "build_dataset_jsonld", lambda ds: {"@id": ds})
    recorded = []
    monkeypatch.setattr(usage, "record_server_event", lambda *a, **k: recorded.append((a[1], k.get("detail"))))
    return {"pub": pub, "recorded": recorded}


def test_묶음_패키지는_데이터셋별_폴더와_구성_목록을_담고_검증된다(env, tmp_path):
    r = TestClient(app).post("/v1/console/bundles/package", json={"dataset_ids": ["urn:a", "urn:b", "urn:a"], "title": "합치기"})
    assert r.status_code == 200
    p = tmp_path / "b.zip"
    p.write_bytes(r.content)
    names = zipfile.ZipFile(p).namelist()
    assert "data/urn_a/items.csv" in names and "data/urn_b/metadata.jsonld" in names
    v = V.verify_package(p, pubkey_pem=env["pub"])
    assert v.ok and v.signer_trusted
    src = v.manifest["source"]
    assert src["kind"] == "bundle" and [m["dataset_id"] for m in src["datasets"]] == ["urn:a", "urn:b"]
    assert v.manifest["dataset_id"].startswith("bundle:")
    assert env["recorded"] == [("urn:a", "bundle"), ("urn:b", "bundle")]


@pytest.mark.parametrize("ids,code", [([], 400), ([f"urn:{i}" for i in range(21)], 400)])
def test_묶음_개수_제한(env, ids, code):
    assert TestClient(app).post("/v1/console/bundles/package", json={"dataset_ids": ids}).status_code == code


def test_볼_수_없는_데이터셋이_있으면_거부(env, monkeypatch):
    def deny(cur, ds, user):
        if ds == "urn:hidden":
            raise HTTPException(404, "데이터셋을 찾을 수 없습니다")
    monkeypatch.setattr(manage, "ensure_visible", deny)
    r = TestClient(app).post("/v1/console/bundles/package", json={"dataset_ids": ["urn:a", "urn:hidden"]})
    assert r.status_code == 404 and env["recorded"] == []


def test_서명_키가_없으면_503(env, monkeypatch):
    monkeypatch.delenv(signing.PRIVATE_KEY_ENV)
    assert TestClient(app).post("/v1/console/bundles/package", json={"dataset_ids": ["urn:a"]}).status_code == 503


def test_아이템_CSV는_BOM과_빈값_처리(env):
    r = TestClient(app).get("/v1/console/datasets/urn:a/items.csv")
    assert r.status_code == 200 and r.content.startswith("﻿".encode())
    assert r.content.decode("utf-8-sig").splitlines() == ["id,title", "1,가", "2,"]
    assert env["recorded"] == [("urn:a", "csv")]


def test_아이템이_없으면_404(env):
    assert TestClient(app).get("/v1/console/datasets/urn:nometa/items.csv").status_code == 404
