"""외부 모듈 연계 (C7, 2026-11-11) — 규격·정책 차단·대체(degrade).

OpenAI 호환 규격은 **진짜 HTTP 서버**(테스트 안에서 띄운 가짜 llama-server)로 확인한다.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from src.external import modules as X
from src.external import service

CTX = {"dataset_id": "urn:t", "title": "HBM 반도체 뉴스", "description": "고대역폭 메모리 시장 동향을 다룬 기사 모음입니다.",
       "keywords": ["HBM"], "samples": ["SK하이닉스 HBM 증설", "삼성 HBM3E 공급"]}


class _Handler(BaseHTTPRequestHandler):
    seen = []
    status = 200
    reply = "요약입니다"

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Handler.seen.append((self.path, dict(self.headers), body))
        payload = ({"choices": [{"message": {"content": _Handler.reply}}]} if self.path.endswith("/chat/completions")
                   else {"text": "분석 결과", "echo": body["task"]})
        data = json.dumps(payload).encode()
        self.send_response(_Handler.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture
def server():
    _Handler.seen, _Handler.status, _Handler.reply = [], 200, "요약입니다"
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def specs(**over):
    base = {
        "local_sllm": {"name": "local_sllm", "adapter": "openai_compat", "endpoint": {"env": "T_LLM_URL"},
                       "model": "m", "auth": {"header": "Authorization", "env": "T_LLM_KEY", "prefix": "Bearer "},
                       "enabled": True, "fallback": "builtin_extractive", "timeout_sec": 5},
        "analysis_tool": {"name": "analysis_tool", "adapter": "http_json", "endpoint": {"env": "T_TOOL_URL"},
                          "enabled": True, "tasks": ["summarize", "keywords", "describe"], "fallback": "builtin_extractive"},
        "cloud": {"name": "cloud", "adapter": "openai_compat", "endpoint": {"env": "T_LLM_URL"}, "network": "external",
                  "enabled": True, "fallback": "builtin_extractive"},
        "builtin_extractive": {"name": "builtin_extractive", "adapter": "builtin_extractive", "enabled": True,
                               "tasks": ["summarize", "keywords", "describe"]},
    }
    for k, v in over.items():
        base[k].update(v)
    return {k: X.ModuleSpec.from_dict(v) for k, v in base.items()}


@pytest.fixture
def builtin_stub(monkeypatch):
    """내장 모듈이 Kiwi 모델을 올리지 않게 — 대체 경로가 불렸는지만 본다."""
    monkeypatch.setitem(X.RUNNERS, "builtin_extractive", lambda spec, task, ctx, q="": {"text": "내장 요약"})


class TestOpenAICompat:
    def test_규격대로_부르고_키는_헤더로만_보낸다(self, server, monkeypatch):
        monkeypatch.setenv("T_LLM_URL", server)
        monkeypatch.setenv("T_LLM_KEY", "k-123")
        r = X.invoke(specs(), "local_sllm", "summarize", CTX)
        assert r["ok"] and not r["degraded"] and r["output"]["text"] == "요약입니다"
        path, headers, body = _Handler.seen[0]
        assert path == "/v1/chat/completions" and headers["Authorization"] == "Bearer k-123"
        assert body["model"] == "m" and body["messages"][0]["role"] == "system"
        assert "HBM 반도체 뉴스" in body["messages"][1]["content"]

    def test_키워드는_목록으로_나눈다(self, server, monkeypatch):
        monkeypatch.setenv("T_LLM_URL", server)
        _Handler.reply = "HBM, 메모리,\n반도체"
        assert X.invoke(specs(), "local_sllm", "keywords", CTX)["output"]["keywords"] == ["HBM", "메모리", "반도체"]

    def test_질문을_함께_보낸다(self, server, monkeypatch):
        monkeypatch.setenv("T_LLM_URL", server)
        X.invoke(specs(), "local_sllm", "ask", CTX, question="주요 기업은?")
        assert "질문: 주요 기업은?" in _Handler.seen[0][2]["messages"][1]["content"]


class TestDegrade:
    def test_서버_오류면_대체_모듈_결과와_사유(self, server, monkeypatch, builtin_stub):
        monkeypatch.setenv("T_LLM_URL", server)
        _Handler.status = 500
        r = X.invoke(specs(), "local_sllm", "summarize", CTX)
        assert r["degraded"] and r["module"] == "builtin_extractive" and r["requested_module"] == "local_sllm"
        assert "500" in r["degraded_reason"] and r["output"]["text"] == "내장 요약"

    def test_연결이_안_되면_대체(self, monkeypatch, builtin_stub):
        monkeypatch.setenv("T_LLM_URL", "http://127.0.0.1:9")
        r = X.invoke(specs(), "local_sllm", "summarize", CTX)
        assert r["degraded"] and "ConnectionError" in r["degraded_reason"]

    def test_주소가_없으면_부르지_않고_대체(self, monkeypatch, builtin_stub):
        monkeypatch.delenv("T_LLM_URL", raising=False)
        r = X.invoke(specs(), "local_sllm", "summarize", CTX)
        assert r["degraded"] and r["degraded_reason"] == "모듈 주소가 설정되지 않았습니다"

    def test_비활성이면_대체(self, builtin_stub):
        r = X.invoke(specs(local_sllm={"enabled": False}), "local_sllm", "summarize", CTX)
        assert r["degraded"] and "비활성" in r["degraded_reason"]

    def test_대체가_없으면_실패로_돌려준다(self, monkeypatch):
        monkeypatch.delenv("T_LLM_URL", raising=False)
        r = X.invoke(specs(local_sllm={"fallback": None}), "local_sllm", "summarize", CTX)
        assert r["ok"] is False and r["output"] is None


class TestPolicy:
    def test_외부망_모듈은_기본으로_막는다(self, server, monkeypatch, builtin_stub):
        monkeypatch.setenv("T_LLM_URL", server)
        monkeypatch.delenv(X.ALLOW_EXTERNAL_ENV, raising=False)
        r = X.invoke(specs(), "cloud", "summarize", CTX)
        assert r["degraded"] and "ADR-013" in r["degraded_reason"] and not _Handler.seen

    def test_허용해도_반출_불가_데이터는_보내지_않는다(self, server, monkeypatch, builtin_stub):
        monkeypatch.setenv("T_LLM_URL", server)
        monkeypatch.setenv(X.ALLOW_EXTERNAL_ENV, "true")
        r = X.invoke(specs(), "cloud", "summarize", CTX, export_allowed=False)
        assert r["degraded"] and "약관" in r["degraded_reason"] and not _Handler.seen
        assert X.invoke(specs(), "cloud", "summarize", CTX, export_allowed=True)["degraded"] is False

    def test_내부망_모듈은_반출_불가_데이터도_쓴다(self, server, monkeypatch):
        monkeypatch.setenv("T_LLM_URL", server)
        assert X.invoke(specs(), "local_sllm", "summarize", CTX, export_allowed=False)["degraded"] is False


class TestHttpJson:
    def test_기존_시스템에_메타데이터를_보내고_결과를_받는다(self, server, monkeypatch):
        monkeypatch.setenv("T_TOOL_URL", server + "/analyze")
        r = X.invoke(specs(), "analysis_tool", "describe", CTX)
        assert r["output"] == {"text": "분석 결과", "echo": "describe"}
        assert _Handler.seen[0][2]["dataset"]["title"] == "HBM 반도체 뉴스"


class TestSpec:
    def test_등록된_설정_파일이_규격을_지킨다(self):
        loaded = X.load_all()
        assert {"builtin_extractive", "local_sllm", "analysis_tool"} <= set(loaded)
        assert all(s.fallback in (None, "builtin_extractive") for s in loaded.values())
        assert loaded["local_sllm"].network == "internal"

    @pytest.mark.parametrize("bad", [{"adapter": "ftp"}, {"network": "cloud"}, {"tasks": ["translate"]},
                                     {"name": "../x"}, {"endpoint": "http://user:pw@host/"}])
    def test_잘못된_설정은_거부한다(self, bad):
        d = {"name": "m", "adapter": "openai_compat", **bad}
        with pytest.raises(X.ModuleError):
            X.ModuleSpec.from_dict(d)

    def test_관리_화면에는_주소와_키_값이_나가지_않는다(self, monkeypatch):
        monkeypatch.setenv("T_LLM_URL", "http://10.1.2.3:8080")
        pub = specs()["local_sllm"].public()
        assert pub["endpoint_configured"] is True and "10.1.2.3" not in json.dumps(pub)

    def test_작업을_하지_않는_모듈은_거부한다(self):
        with pytest.raises(X.ModuleError):
            X.invoke(specs(), "builtin_extractive", "ask", CTX)

    def test_없는_모듈은_404(self):
        with pytest.raises(X.ModuleError) as e:
            X.invoke(specs(), "nope", "summarize", CTX)
        assert e.value.code == 404


def test_내장_모듈은_원문에서만_뽑는다():
    r = X.run_builtin(specs()["builtin_extractive"], "keywords", CTX)
    words = " ".join([CTX["description"]] + CTX["samples"]).lower()
    assert r["keywords"] and all(k in words and len(k) >= 2 for k in r["keywords"])


class TestService:
    def test_대체_결과는_저장하지_않는다(self, monkeypatch, builtin_stub):
        monkeypatch.setattr(service, "dataset_context", lambda ds: (CTX, True))
        monkeypatch.delenv("T_LLM_URL", raising=False)
        r = service.run("local_sllm", "summarize", "urn:t", save=True, specs=specs())
        assert r["degraded"] and r["saved"] is False

    def test_API는_관리자만(self):
        from src.api.main import app
        c = TestClient(app)
        assert c.get("/v1/console/modules").status_code == 401
        assert c.post("/v1/console/modules/local_sllm/run", json={}).status_code == 401
