"""패키지 데이터 점검 정보 — 받는 쪽이 열어 보지 않고도 데이터 상태를 안다.

연구계획서 4차년도 "능동형 패키징": "데이터의 기술통계를 비롯한 데이터 테스트 정보를 포함하여
데이터를 분석하지 않아도 기본 정보를 파악". B1 특징(manifest `features`)은 데이터셋 수준이고,
여기서는 **실제로 담긴 파일**을 점검한다.

- CSV: 행·열 수, 열마다 빈 값 비율·고유값 수(1만 개에서 멈춤), 중복 행 수
- JSON/JSON-LD: 해석되는지
- 점검(`checks`): 통과/실패와 근거. 기대 행 수(등록 건수)가 주어지면 맞는지도 본다

값 자체(예시 행)는 담지 않는다 — manifest는 공개될 수 있고, 원문은 데이터 파일에만 있어야 한다.
"""

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_DISTINCT_CAP = 10_000


def _profile_csv(path: Path) -> Dict[str, Any]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if header is None:
            return {"format": "csv", "rows": 0, "columns": [], "parse_ok": True}
        n = len(header)
        empty = [0] * n
        distinct: List[set] = [set() for _ in range(n)]
        seen_rows: set = set()
        dup = rows = ragged = 0
        for row in reader:
            rows += 1
            if len(row) != n:
                ragged += 1
            key = hash(tuple(row))
            if key in seen_rows:
                dup += 1
            else:
                seen_rows.add(key)
            for i in range(n):
                v = row[i] if i < len(row) else ""
                if v == "":
                    empty[i] += 1
                elif len(distinct[i]) < _DISTINCT_CAP:
                    distinct[i].add(v)
    cols = [{"name": header[i],
             "empty_ratio": round(empty[i] / rows, 4) if rows else 0.0,
             "distinct": len(distinct[i]),
             "distinct_capped": len(distinct[i]) >= _DISTINCT_CAP} for i in range(n)]
    return {"format": "csv", "rows": rows, "columns": cols, "duplicate_rows": dup,
            "ragged_rows": ragged, "header_unique": len(set(header)) == n, "parse_ok": True}


def _profile_json(path: Path) -> Dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {"format": "json", "parse_ok": False}
    kind = type(obj).__name__
    size = len(obj) if isinstance(obj, (list, dict)) else None
    return {"format": "json", "parse_ok": True, "top_level": kind, "top_level_size": size}


def profile(source_dir: Path, data_prefix: str, expected_rows: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """`source_dir` 파일들을 점검한다. expected_rows: {상대경로: 기대 행 수}."""
    files: Dict[str, Any] = {}
    checks: List[Dict[str, Any]] = []
    for path in sorted(Path(source_dir).rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source_dir).as_posix()
        name = f"{data_prefix}/{rel}"
        suffix = path.suffix.lower()
        try:
            if suffix == ".csv":
                p = _profile_csv(path)
            elif suffix in (".json", ".jsonld"):
                p = _profile_json(path)
            else:
                continue
        except (UnicodeDecodeError, csv.Error) as e:
            p = {"format": suffix.lstrip("."), "parse_ok": False, "error": type(e).__name__}
        files[name] = p
        checks.append({"name": "형식 해석", "target": name, "passed": bool(p.get("parse_ok"))})
        if p.get("format") == "csv" and p.get("parse_ok"):
            checks.append({"name": "열 이름 중복 없음", "target": name, "passed": bool(p["header_unique"])})
            checks.append({"name": "행마다 열 수 일치", "target": name, "passed": p["ragged_rows"] == 0,
                           "detail": f"어긋난 행 {p['ragged_rows']}"})
            want = (expected_rows or {}).get(rel)
            if want is not None:
                checks.append({"name": "등록 건수와 행 수 일치", "target": name,
                               "passed": p["rows"] == want, "detail": f"행 {p['rows']} / 등록 {want}"})
    return {"files": files, "checks": checks,
            "passed": sum(c["passed"] for c in checks), "failed": sum(not c["passed"] for c in checks)}


def summarize(q: Dict[str, Any]) -> str:
    return f"점검 {q['passed'] + q['failed']}건 — 통과 {q['passed']} · 실패 {q['failed']}"
