"""원천 스키마 드리프트 감지 (C4 최소선).

**근거**: 연구개발계획서 4차년도 "데이터 동적 변화 분석·자동 반영"
〔SW 모듈 귀속: 모비젠〕. C4 완료 기준의 후반부 —
"소스 스키마 변경이 **자동 감지·기록**됨".

---

## 왜 필요한가 — 이 고장은 소리를 내지 않는다

어댑터 스펙은 원천 응답의 경로를 문자열로 박아 둔다.

    fields:
      title: snippet.title

원천이 `snippet.title`을 없애거나 옮기면 `dig()`가 `None`을 돌려주고,
그 컬럼은 **오류 없이 NULL**로 들어간다. 수집은 "성공"으로 끝나고,
`item_count`도 평소대로 늘어난다. 사람이 알아채는 시점은 한참 뒤
"검색 결과가 왜 이래?"다. 2026-11-04에 `<b>` 태그 오염 28건을 **실물을 눈으로
보고서야** 찾은 것과 같은 종류의 고장이다.

그래서 수집할 때마다 원천 응답의 **모양**을 재서 지난번과 비교한다.

## 두 가지를 따로 본다

| | 질문 | 성격 |
|---|---|---|
| **drift** | 원천 모양이 지난번과 달라졌나 | **사건** — 한 번 일어나고 지나간다 |
| **mapping** | 우리가 쓰는 경로가 지금도 오는가 | **상태** — 고칠 때까지 계속 참이다 |

지문만 비교하면 안 되는 이유가 여기 있다. 지문은 바뀐 순간 한 번 울리고,
새 지문을 저장하면 다음 수집부터 "변경 없음"이 된다 — **깨진 매핑을 그대로 둔 채**
경보만 사라진다. 그래서 "스펙이 쓰는 경로가 지금 관측에 있는가"는 지문과 무관하게
**매번** 확인한다.

## 필드 하나가 빠졌다고 스키마가 바뀐 건 아니다

레코드마다 선택 필드가 있다. 60건의 **합집합**을 지문으로 쓰면 그중 한 건에만
있던 필드 때문에 매 수집마다 지문이 달라진다 — 경보가 무뎌지고, 무뎌진 경보는
없는 것과 같다. 그래서 **관측 비율이 `CORE_RATIO` 이상인 필드**만 스키마로 본다.
표본이 `MIN_SAMPLE`보다 적으면 비율을 믿을 수 없으므로 아예 판정하지 않는다.

## 리스트 인덱스는 경로에 넣지 않는다

`items.0.title`, `items.1.title` … 을 각각 세면 **결과 건수만 달라져도** 지문이
흔들린다. 리스트 원소는 `[]` 하나로 접는다 — `items[].title`.
"""

import difflib
import hashlib
import json
import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger(__name__)

#: 이 비율 이상의 레코드에서 관측된 경로만 "스키마"로 본다. 선택 필드를 걸러낸다.
CORE_RATIO = 0.9

#: 표본이 이보다 적으면 판정하지 않는다. 3건 중 1건에만 있는 필드의 비율 0.33은
#: "선택 필드"의 증거가 아니라 그냥 표본 부족이다.
MIN_SAMPLE = 5

#: 한 번 스키마로 본 필드를 지켜 주는 폭. `CORE_RATIO - STICKY_BAND` 이상이면
#: 계속 스키마로 본다. **임계선 근처에서 깜빡이는 것**을 막는다 —
#: 2026-11-04 YouTube 실측에서 `snippet.thumbnails.maxres`가 93.6%,
#: `standard`가 97.9%로 90% 바로 위였다. 다음 수집에 88%가 되면 아무 일도
#: 없었는데 "필드 제거"가 뜬다. 들어오는 문턱은 높게, 나가는 문턱은 낮게 둔다.
STICKY_BAND = 0.2

#: 중첩 탐색 깊이 상한. 원천이 깊은 트리를 돌려줘도 경로 수가 폭발하지 않게 한다.
MAX_DEPTH = 4

#: 리스트에서 훑어볼 원소 수. 전수로 볼 이유가 없다 — 모양만 본다.
LIST_SAMPLE = 5

#: 리스트 원소를 가리키는 표시. `items.0.title` → `items[].title`
LIST_MARK = "[]"

_DIGIT = re.compile(r"^\d+$")

#: 이 감지기가 기록할 자리를 만드는 마이그레이션. 미적용일 때 사람에게 보여 준다.
MIGRATION = "sql/migration_2026_11_04_source_schema_drift.sql"

#: PostgreSQL `undefined_column`.
_UNDEFINED_COLUMN = "42703"


# ── 관측 ────────────────────────────────────────────────────────────────────

def field_paths(obj: Any, prefix: str = "", depth: int = 0) -> Set[str]:
    """레코드 하나에서 필드 경로를 전부 뽑는다.

    컨테이너 자신도 경로로 넣는다 — `snippet`과 `snippet.title`이 둘 다 나온다.
    그래야 `tags: []`처럼 **비어 있을 때도** 키가 있다는 사실이 남는다.
    """
    out: Set[str] = set()
    if depth > MAX_DEPTH:
        return out
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            out.add(path)
            out |= field_paths(value, path, depth + 1)
    elif isinstance(obj, list):
        for item in obj[:LIST_SAMPLE]:
            out |= field_paths(item, prefix + LIST_MARK, depth + 1)
    return out


def observe(raws: Sequence[Dict[str, Any]]) -> Dict[str, float]:
    """경로별 관측 비율. 1.0이면 모든 레코드에 있었다는 뜻."""
    n = len(raws)
    if not n:
        return {}
    counts: Dict[str, int] = {}
    for raw in raws:
        for path in field_paths(raw):
            counts[path] = counts.get(path, 0) + 1
    return {p: c / n for p, c in counts.items()}


def core_fields(observed: Dict[str, float], ratio: float = CORE_RATIO,
                previous: Optional[Iterable[str]] = None) -> List[str]:
    """선택 필드를 걷어낸 **핵심 경로 집합**. 정렬해서 돌려준다.

    `previous`(직전 집합)를 주면 이미 스키마로 보던 필드는 `STICKY_BAND`만큼
    낮은 비율까지 버텨 준다. 안 주면 들어오는 문턱만 적용된다.
    """
    prev = set(previous or ())
    floor = max(0.0, ratio - STICKY_BAND)
    return sorted(p for p, r in observed.items()
                  if r >= ratio or (p in prev and r >= floor))


def fingerprint(fields: Iterable[str]) -> str:
    """핵심 경로 집합의 지문.

    정렬된 경로를 줄바꿈으로 이어 해시한다 — JSON 직렬화를 쓰지 않는 이유는
    공백·키 순서 같은 표현 차이가 지문을 바꾸면 안 되기 때문이다
    (C5 `canonical_bytes`와 같은 이유).
    """
    joined = "\n".join(sorted(fields))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


# ── 비교 ────────────────────────────────────────────────────────────────────

def normalize_spec_path(path: str) -> str:
    """스펙의 경로를 관측 경로와 같은 표기로 맞춘다.

    스펙은 `dig()`가 읽는 표기(`items.0.title`)를 쓰고, 관측은 인덱스를 접은
    표기(`items[].title`)를 쓴다. 맞춰 두지 않으면 **멀쩡한 매핑이 깨진 것으로**
    보고된다.
    """
    parts = []
    for part in path.split("."):
        if _DIGIT.match(part):
            if parts:
                parts[-1] = parts[-1] + LIST_MARK
            continue
        parts.append(part)
    return ".".join(parts)


def mapped_paths(source_spec: Dict[str, Any]) -> List[str]:
    """어댑터 스펙이 실제로 읽는 원천 경로. 이것들이 깨지면 데이터가 빈다."""
    paths: Set[str] = set()
    for value in (source_spec.get("fields") or {}).values():
        if isinstance(value, str):
            paths.add(normalize_spec_path(value))
    id_field = source_spec.get("id_field")
    if isinstance(id_field, str):
        paths.add(normalize_spec_path(id_field))
    return sorted(paths)


def diff(previous: Sequence[str], current: Sequence[str]) -> Dict[str, List[str]]:
    prev, cur = set(previous or []), set(current or [])
    return {"added": sorted(cur - prev), "removed": sorted(prev - cur)}


def _key(name: str) -> str:
    """이름 비교용 정규화. 원천마다 표기 관례가 다르다 — `pubDate` / `published_at`
    / `publishedAt`은 같은 것을 가리키는데 글자 그대로는 닮지 않았다."""
    return name.lower().replace("_", "")


def _match(target: str, candidates: Sequence[str], keyed: Dict[str, str],
           limit: int, cutoff: float) -> List[str]:
    scored = []
    for c in candidates:
        ratio = difflib.SequenceMatcher(None, target, keyed[c]).ratio()
        if ratio >= cutoff:
            scored.append((ratio, c))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [c for _, c in scored[:limit]]


def suggest(broken: Sequence[str], candidates: Sequence[str],
            limit: int = 3) -> Dict[str, List[str]]:
    """깨진 경로마다 **대체 후보**를 고른다 — 스펙 갱신 제안의 재료.

    이름이 닮은 것을 고를 뿐이다(`pubDate` ↔ `publishedAt`). 고쳐 주지 않는다 —
    원천이 의미까지 그대로 옮겼는지는 사람이 봐야 안다. 전체 경로로 먼저 보고,
    못 찾으면 잎 이름만으로 한 번 더 본다(필드가 다른 가지로 옮겨 간 경우).
    """
    out: Dict[str, List[str]] = {}
    cand = list(candidates)
    by_path = {c: _key(c) for c in cand}
    by_leaf = {c: _key(c.split(".")[-1]) for c in cand}
    for path in broken:
        hits = _match(_key(path), cand, by_path, limit, 0.5)
        if not hits:
            hits = _match(_key(path.split(".")[-1]), cand, by_leaf, limit, 0.6)
        if hits:
            out[path] = hits
    return out


# ── 저장 ────────────────────────────────────────────────────────────────────

def load_previous(conn, dataset_id: str) -> Optional[Tuple[Optional[str], List[str]]]:
    """직전 지문과 경로 집합. 레지스트리에 행이 없으면 None."""
    cur = conn.cursor()
    cur.execute(
        "SELECT source_schema_fingerprint, source_schema_fields "
        "FROM data_registry WHERE dataset_id = %s", (dataset_id,))
    row = cur.fetchone()
    cur.close()
    if row is None:
        return None
    return row[0], list(row[1] or [])


def _is_missing_columns(exc: Exception) -> bool:
    """기록할 컬럼이 아직 없는 것인지(= 마이그레이션 미적용), 다른 고장인지."""
    if getattr(exc, "pgcode", None) == _UNDEFINED_COLUMN:
        return True
    return "source_schema" in str(exc)


def save(conn, dataset_id: str, fp: str, fields: Sequence[str], changed: bool) -> None:
    """지문을 기록한다. `changed_at`은 **달라졌을 때만** 건드린다."""
    cur = conn.cursor()
    cur.execute(
        "UPDATE data_registry SET "
        "  source_schema_fingerprint = %s, "
        "  source_schema_fields      = %s::jsonb, "
        "  source_schema_checked_at  = now(), "
        "  source_schema_changed_at  = CASE WHEN %s THEN now() "
        "                                   ELSE source_schema_changed_at END, "
        "  updated_at = now() "
        "WHERE dataset_id = %s",
        (fp, json.dumps(list(fields), ensure_ascii=False), changed, dataset_id))
    conn.commit()
    cur.close()


# ── 본체 ────────────────────────────────────────────────────────────────────

def check(dataset_id: str, raws: Sequence[Dict[str, Any]],
          source_spec: Optional[Dict[str, Any]] = None,
          conn=None, dry_run: bool = False,
          min_sample: int = MIN_SAMPLE, ratio: float = CORE_RATIO) -> Dict[str, Any]:
    """수집 결과의 모양을 재고 지난번과 비교한다.

    **수집을 실패시키지 않는다.** 이건 관측이지 관문이 아니다 — 여기서 예외를
    올리면 원천이 필드 하나 바꿨다고 수집이 멈춘다. 호출부가 결과를 보고
    판단한다.

    돌려주는 `status`
        skipped          표본이 적어 판정하지 않음
        not_provisioned  기록할 `source_schema_*` 컬럼이 아직 없음(마이그레이션 미적용).
                         **측정 결과는 돌려준다** — 지문도 깨진 매핑도 들어 있다
        unregistered     data_registry에 행이 없음 (스펙의 dataset_id 오타 등)
        first_seen       첫 관측 — 비교 대상이 없다
        unchanged        지문 동일
        changed          지문이 달라졌다

    `severity`
        none       이상 없음
        additive   필드가 늘기만 했다 — 기록만 한다
        removed    쓰지 않는 필드가 빠졌다 — 지금은 무해하나 원천이 움직이는 중이다
        breaking   **스펙이 읽는 경로가 지금 안 온다** — 해당 컬럼이 조용히 빈다
    """
    result: Dict[str, Any] = {"dataset_id": dataset_id, "sample": len(raws),
                              "status": "skipped", "severity": "none"}
    if len(raws) < min_sample:
        result["reason"] = f"표본 {len(raws)}건 < {min_sample}건 — 비율을 믿을 수 없다"
        return result

    observed = observe(raws)

    # 직전 집합을 **먼저** 읽는다 — 히스테리시스가 그걸 입력으로 받는다
    if conn is None:
        from src.database.db import get_conn
        conn = get_conn()
    try:
        previous = load_previous(conn, dataset_id)
    except Exception as e:                        # noqa: BLE001
        # ⚠️ 실패한 SELECT는 트랜잭션을 ERROR 상태로 남긴다. 커넥션은 프로세스당
        # 하나를 **공유**하므로(src/database/db.py), 되돌려 놓지 않으면 뒤따르는
        # store 단계가 "current transaction is aborted"로 죽는다 —
        # 관측이 적재를 죽이는 일이 바로 이렇게 생긴다.
        try:
            conn.rollback()
        except Exception:                         # noqa: BLE001
            pass
        if not _is_missing_columns(e):
            raise
        result["status"] = "not_provisioned"
        result["reason"] = (f"data_registry에 source_schema_* 컬럼이 없다 — "
                            f"{MIGRATION} 적용 필요")
        logger.warning("drift: %s — 측정은 했으나 기록할 자리가 없다. %s 적용 필요",
                       dataset_id, MIGRATION)
        previous = None
    prev_fp, prev_fields = previous if previous else (None, [])

    fields = core_fields(observed, ratio, previous=prev_fields)
    fp = fingerprint(fields)
    result.update({"fingerprint": fp, "field_count": len(fields)})

    # 상태 점검 — 지문 변화와 **무관하게** 매번 본다.
    # 깨진 매핑은 사건이 아니라 상태다. 고칠 때까지 계속 참이어야 한다.
    wanted = mapped_paths(source_spec or {})
    broken = [p for p in wanted if p not in fields]
    if broken:
        result["broken_mappings"] = broken
        result["severity"] = "breaking"
        result["suggestions"] = suggest(broken, fields)
        logger.error("drift: %s 스펙이 읽는 경로 %d개가 지금 안 온다 — 컬럼이 조용히 빈다",
                     dataset_id, len(broken))
        for path in broken:
            hint = ", ".join(result["suggestions"].get(path, [])) or "후보 없음"
            logger.error("   ✗ %s  → 후보: %s", path, hint)

    if previous is None:
        # not_provisioned(기록할 컬럼 없음) / unregistered(레지스트리에 행 없음).
        # 둘 다 **측정은 끝났다** — 지문과 깨진 매핑은 돌려준다. 기록만 못 한다.
        if result["status"] != "not_provisioned":
            result["status"] = "unregistered"
            logger.warning("drift: data_registry에 %s 행이 없다 — 기록하지 않는다", dataset_id)
        result["persisted"] = False
        return result

    changed = bool(prev_fp) and prev_fp != fp
    result["status"] = "changed" if changed else ("unchanged" if prev_fp else "first_seen")

    if changed:
        d = diff(prev_fields, fields)
        result.update(d)
        if result["severity"] != "breaking":
            result["severity"] = "removed" if d["removed"] else "additive"
        logger.warning("drift: %s 원천 모양 변경 — 추가 %d · 제거 %d (%s)",
                       dataset_id, len(d["added"]), len(d["removed"]), result["severity"])
        for path in d["added"]:
            logger.info("   + %s (%.0f%% 관측)", path, 100 * observed.get(path, 0))
        for path in d["removed"]:
            logger.info("   - %s (%.0f%% 관측)", path, 100 * observed.get(path, 0))

    if dry_run:
        result["persisted"] = False
        return result

    save(conn, dataset_id, fp, fields, changed)
    result["persisted"] = True
    return result
