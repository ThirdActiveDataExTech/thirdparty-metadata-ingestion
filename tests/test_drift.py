"""원천 스키마 드리프트 감지 (C4 최소선).

여기서 막으려는 것 넷.

1. **조용한 고장** — 원천이 경로를 바꾸면 `dig()`가 None을 주고 컬럼이
   오류 없이 NULL로 들어간다. 수집은 "성공"으로 끝난다.
2. **경보 피로** — 선택 필드 하나 때문에 매 수집마다 "변경됨"이 뜨면
   아무도 안 본다. 무뎌진 경보는 없는 것과 같다.
3. **경보가 한 번 울고 사라지는 것** — 지문을 갱신하면 다음 수집부터
   "변경 없음"이 된다. **깨진 매핑은 그대로인데** 경보만 없어진다.
4. **감지기가 수집을 죽이는 것** — 관측이지 관문이 아니다.
"""

import pytest

from src.pipeline_engine import drift


# ── 테스트용 가짜 DB ────────────────────────────────────────────────────────

class _UndefinedColumn(Exception):
    pgcode = "42703"          # PostgreSQL undefined_column


class _FakeCursor:
    def __init__(self, store, dataset_id_present=True, missing_columns=False):
        self.store = store
        self.present = dataset_id_present
        self.missing = missing_columns
        self._row = None

    def execute(self, sql, params=None):
        if self.missing:
            raise _UndefinedColumn('column "source_schema_fingerprint" does not exist')
        if sql.strip().upper().startswith("SELECT"):
            self._row = (self.store.get("fingerprint"),
                         self.store.get("fields")) if self.present else None
        else:
            fp, fields_json, changed, _ds = params
            self.store["fingerprint"] = fp
            self.store["fields"] = __import__("json").loads(fields_json)
            self.store["checked"] = True
            if changed:
                self.store["changed"] = True

    def fetchone(self):
        return self._row

    def close(self):
        pass


class _FakeConn:
    def __init__(self, store=None, present=True, missing_columns=False):
        self.store = store if store is not None else {}
        self.present = present
        self.missing_columns = missing_columns
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return _FakeCursor(self.store, self.present, self.missing_columns)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def _records(n, extra=None, drop=()):
    """같은 모양의 레코드 n건. extra는 **한 건에만** 붙는 선택 필드."""
    out = []
    for i in range(n):
        r = {"link": f"http://x/{i}", "title": f"제목{i}",
             "description": "본문", "originallink": "http://o", "pubDate": "2026-11-04"}
        for k in drop:
            r.pop(k, None)
        out.append(r)
    if extra:
        out[0].update(extra)
    return out


_SPEC = {"fields": {"article_url": "link", "title": "title",
                    "description": "description", "naver_url": "originallink",
                    "published_at": "pubDate"},
         "id_field": "link"}


# ── 관측 ────────────────────────────────────────────────────────────────────

class TestFieldPaths:
    def test_중첩을_점으로_편다(self):
        paths = drift.field_paths({"snippet": {"title": "t"}})
        assert "snippet" in paths and "snippet.title" in paths

    def test_리스트_인덱스를_접는다(self):
        """`items.0.x`, `items.1.x`를 각각 세면 **건수만 달라져도** 지문이 흔들린다."""
        one = drift.field_paths({"tags": [{"name": "a"}]})
        many = drift.field_paths({"tags": [{"name": "a"}, {"name": "b"}, {"name": "c"}]})
        assert one == many == {"tags", "tags[].name"}

    def test_빈_리스트도_키는_남는다(self):
        assert "tags" in drift.field_paths({"tags": []})

    def test_깊이를_제한한다(self):
        deep = {"a": {"b": {"c": {"d": {"e": {"f": 1}}}}}}
        assert not any(p.count(".") > drift.MAX_DEPTH for p in drift.field_paths(deep))

    def test_null도_키가_있는_것으로_본다(self):
        # 키를 빼는 것과 null을 보내는 것은 원천 입장에서 다른 사건이다
        assert "x" in drift.field_paths({"x": None})


class TestCoreFields:
    def test_선택_필드를_걸러낸다(self):
        """경보 피로를 막는 핵심 — 1/20에만 있는 필드는 스키마가 아니다."""
        obs = drift.observe(_records(20, extra={"가끔오는필드": 1}))
        assert obs["가끔오는필드"] == pytest.approx(0.05)
        assert "가끔오는필드" not in drift.core_fields(obs)
        assert "title" in drift.core_fields(obs)

    def test_비율_경계를_넘으면_포함한다(self):
        obs = {"a": drift.CORE_RATIO, "b": drift.CORE_RATIO - 0.01}
        assert drift.core_fields(obs) == ["a"]


class TestHysteresis:
    """임계선 근처에서 깜빡이는 것을 막는다.

    2026-11-04 YouTube 실측: `snippet.thumbnails.maxres` 93.6%,
    `standard` 97.9% — 문턱 90% 바로 위다. 다음 수집에 88%가 되면
    아무 일도 없었는데 '필드 제거'가 뜬다.
    """

    def test_이미_보던_필드는_조금_내려가도_버틴다(self):
        obs = {"maxres": drift.CORE_RATIO - 0.1}
        assert drift.core_fields(obs) == []                       # 새로 들어오진 못하고
        assert drift.core_fields(obs, previous=["maxres"]) == ["maxres"]   # 있던 건 버틴다

    def test_진짜로_사라지면_빠진다(self):
        obs = {"maxres": 0.05}
        assert drift.core_fields(obs, previous=["maxres"]) == []

    def test_흔들려도_지문이_그대로다(self):
        conn = _FakeConn()
        많음 = [dict(r, maxres="u") for r in _records(10)]
        적음 = [dict(r, maxres="u") for r in _records(10)]
        for r in 적음[:2]:
            r.pop("maxres")                                        # 80%로 내려간다
        first = drift.check("ds", 많음, _SPEC, conn=conn)
        second = drift.check("ds", 적음, _SPEC, conn=conn)
        assert second["fingerprint"] == first["fingerprint"]
        assert second["status"] == "unchanged"


class TestFingerprint:
    def test_순서에_흔들리지_않는다(self):
        assert drift.fingerprint(["b", "a"]) == drift.fingerprint(["a", "b"])

    def test_집합이_다르면_달라진다(self):
        assert drift.fingerprint(["a"]) != drift.fingerprint(["a", "b"])


class TestSpecPaths:
    def test_스펙의_인덱스_표기를_맞춘다(self):
        """맞춰 두지 않으면 **멀쩡한 매핑이 깨진 것으로** 보고된다."""
        assert drift.normalize_spec_path("items.0.title") == "items[].title"

    def test_스펙이_읽는_경로를_모은다(self):
        assert drift.mapped_paths(_SPEC) == [
            "description", "link", "originallink", "pubDate", "title"]

    def test_id_field도_포함한다(self):
        assert "id.videoId" in drift.mapped_paths(
            {"fields": {"title": "snippet.title"}, "id_field": "id.videoId"})


class TestSuggest:
    def test_닮은_이름을_후보로_준다(self):
        out = drift.suggest(["pubDate"], ["publishedAt", "title", "link"])
        assert "publishedAt" in out["pubDate"]

    def test_후보가_없으면_비워_둔다(self):
        assert drift.suggest(["pubDate"], ["zzz"]) == {}


# ── 판정 ────────────────────────────────────────────────────────────────────

class TestCheck:
    def test_표본이_적으면_판정하지_않는다(self):
        r = drift.check("ds", _records(2), _SPEC, conn=_FakeConn())
        assert r["status"] == "skipped" and "표본" in r["reason"]

    def test_첫_관측은_비교하지_않는다(self):
        conn = _FakeConn()
        r = drift.check("ds", _records(10), _SPEC, conn=conn)
        assert r["status"] == "first_seen" and r["severity"] == "none"
        assert conn.store["fingerprint"] and "changed" not in conn.store

    def test_같은_모양이면_변경_없음(self):
        conn = _FakeConn()
        drift.check("ds", _records(10), _SPEC, conn=conn)
        r = drift.check("ds", _records(10), _SPEC, conn=conn)
        assert r["status"] == "unchanged" and r["severity"] == "none"
        assert "changed" not in conn.store

    def test_필드가_늘면_additive(self):
        conn = _FakeConn()
        drift.check("ds", _records(10), _SPEC, conn=conn)
        늘어난 = [dict(r, 새필드="v") for r in _records(10)]
        r = drift.check("ds", 늘어난, _SPEC, conn=conn)
        assert r["status"] == "changed" and r["severity"] == "additive"
        assert r["added"] == ["새필드"] and r["removed"] == []
        assert conn.store["changed"] is True

    def test_안_쓰는_필드가_빠지면_removed(self):
        conn = _FakeConn()
        drift.check("ds", [dict(r, 안쓰는필드="v") for r in _records(10)], _SPEC, conn=conn)
        r = drift.check("ds", _records(10), _SPEC, conn=conn)
        assert r["severity"] == "removed" and r["removed"] == ["안쓰는필드"]

    def test_스펙이_읽는_경로가_빠지면_breaking(self):
        """조용한 고장 — 수집은 성공하는데 그 컬럼만 NULL이 된다."""
        conn = _FakeConn()
        drift.check("ds", _records(10), _SPEC, conn=conn)
        r = drift.check("ds", _records(10, drop=("pubDate",)), _SPEC, conn=conn)
        assert r["severity"] == "breaking"
        assert r["broken_mappings"] == ["pubDate"]

    def test_지문이_그대로여도_깨진_매핑은_매번_보고한다(self):
        """경보가 한 번 울고 사라지지 않게 — 깨진 매핑은 사건이 아니라 **상태**다.

        변경을 기록하면 지문이 갱신돼 다음 수집은 'unchanged'가 된다.
        그때도 pubDate는 여전히 안 온다. 경보가 여기서 꺼지면
        아무도 스펙을 고치지 않는다.
        """
        conn = _FakeConn()
        깨진모양 = _records(10, drop=("pubDate",))
        drift.check("ds", 깨진모양, _SPEC, conn=conn)          # 첫 관측
        r = drift.check("ds", 깨진모양, _SPEC, conn=conn)      # 지문 동일
        assert r["status"] == "unchanged"
        assert r["severity"] == "breaking"
        assert r["broken_mappings"] == ["pubDate"]

    def test_깨진_매핑에_대체_후보를_붙인다(self):
        conn = _FakeConn()
        옮겨짐 = [dict(r, publishedAt=r.pop("pubDate")) for r in _records(10)]
        r = drift.check("ds", 옮겨짐, _SPEC, conn=conn)
        assert r["suggestions"]["pubDate"] == ["publishedAt"]

    def test_레지스트리에_행이_없으면_기록하지_않는다(self):
        conn = _FakeConn(present=False)
        r = drift.check("ds", _records(10), _SPEC, conn=conn)
        assert r["status"] == "unregistered"
        assert conn.store == {} and conn.commits == 0

    def test_dry_run은_쓰지_않는다(self):
        conn = _FakeConn()
        r = drift.check("ds", _records(10), _SPEC, conn=conn, dry_run=True)
        assert r["persisted"] is False
        assert conn.store == {} and conn.commits == 0

    def test_드리프트가_없어도_지문은_갱신한다(self):
        """`checked_at`이 멈춰 있으면 감지기 자체가 안 도는 것이다."""
        conn = _FakeConn()
        drift.check("ds", _records(10), _SPEC, conn=conn)
        conn.store.pop("checked")
        drift.check("ds", _records(10), _SPEC, conn=conn)
        assert conn.store.get("checked") is True


class TestRunnerIntegration:
    def test_감지_실패가_수집을_무효로_만들지_않는다(self):
        """관측이지 관문이 아니다 — 원천 모양을 못 쟀다고 수집을 버리지 않는다."""
        from src.pipeline_engine import runner

        class _Boom:
            spec = _SPEC

        def _explode(*a, **k):
            raise RuntimeError("DB 끊김")

        원래 = drift.check
        drift.check = _explode
        try:
            r = runner._check_drift("ds", _records(10), _Boom(), dry_run=False)
        finally:
            drift.check = 원래
        assert r["status"] == "error" and r["severity"] == "none"


class TestNotProvisioned:
    """마이그레이션 적용 전 — 측정은 되고 기록만 못 한다.

    ⚠️ 여기서 실제로 위험한 것은 '기록 못 함'이 아니다. 커넥션은 프로세스당
    하나를 공유하므로(src/database/db.py), **실패한 SELECT가 트랜잭션을 ERROR
    상태로 남기면 뒤따르는 store가 통째로 죽는다.** 관측이 적재를 죽이는 일이
    바로 이렇게 생긴다.
    """

    def test_트랜잭션을_되돌려_놓는다(self):
        conn = _FakeConn(missing_columns=True)
        drift.check("ds", _records(10), _SPEC, conn=conn)
        assert conn.rollbacks == 1

    def test_상태와_사유를_남긴다(self):
        conn = _FakeConn(missing_columns=True)
        r = drift.check("ds", _records(10), _SPEC, conn=conn)
        assert r["status"] == "not_provisioned"
        assert drift.MIGRATION in r["reason"]
        assert r["persisted"] is False

    def test_측정_결과는_그대로_돌려준다(self):
        conn = _FakeConn(missing_columns=True)
        r = drift.check("ds", _records(10, drop=("pubDate",)), _SPEC, conn=conn)
        assert r["fingerprint"] and r["field_count"] == 4
        assert r["severity"] == "breaking" and r["broken_mappings"] == ["pubDate"]

    def test_다른_DB_오류는_삼키지_않는다(self):
        """컬럼 부재가 아닌 고장을 'not_provisioned'로 덮으면 진단이 막힌다."""
        class _Broken(_FakeConn):
            def cursor(self):
                raise RuntimeError("연결이 끊겼다")

        with pytest.raises(RuntimeError):
            drift.check("ds", _records(10), _SPEC, conn=_Broken())
