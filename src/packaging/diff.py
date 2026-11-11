"""두 패키지 비교 — 같은 데이터셋의 버전 사이에 무엇이 바뀌었는지 (C5 · 4차년도 "데이터 히스토리").

연구계획서 4차년도: "데이터 히스토리와 데이터 리니지 정보 등을 함께 패키징하여 **데이터의 수정 사항을
파악**할 수 있는 패키징". manifest만 비교한다 — 데이터 파일을 열지 않아도 무엇이 바뀌었는지 안다.

- 파일: 추가·삭제·내용 변경(SHA-256), 크기 변화
- 점검(quality): CSV 행 수·열 구성 변화, 점검 통과/실패 변화
- 이력(lineage): 두 패키지 사이에 새로 기록된 수집 실행
- 출처·라이선스 등 레퍼런스 값이 바뀐 항목

**두 패키지 모두 서명 검증을 통과해야** 비교한다. 검증 안 된 manifest의 차이는 의미가 없다.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from src.packaging import verify as V


class DiffError(RuntimeError):
    pass


def _load(path: Path, key: Optional[str], pubkey_pem: Optional[bytes]) -> Dict[str, Any]:
    r = V.verify_package(path, key=key, pubkey_pem=pubkey_pem)
    if not r.ok:
        raise DiffError(f"{Path(path).name}: 검증을 통과하지 못했습니다 — " + "; ".join(r.problems[:3]))
    return r.manifest


def diff_manifests(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    if old["dataset_id"] != new["dataset_id"]:
        raise DiffError("서로 다른 데이터셋의 패키지입니다")
    of = {f["path"]: f for f in old["files"]}
    nf = {f["path"]: f for f in new["files"]}
    files = {
        "added": sorted(set(nf) - set(of)),
        "removed": sorted(set(of) - set(nf)),
        "changed": [{"path": p, "bytes_before": of[p].get("bytes"), "bytes_after": nf[p].get("bytes")}
                    for p in sorted(set(of) & set(nf)) if of[p]["sha256"] != nf[p]["sha256"]],
        "unchanged": sum(1 for p in set(of) & set(nf) if of[p]["sha256"] == nf[p]["sha256"]),
    }

    tables: List[Dict[str, Any]] = []
    oq = (old.get("quality") or {}).get("files") or {}
    nq = (new.get("quality") or {}).get("files") or {}
    for p in sorted(set(oq) | set(nq)):
        a, b = oq.get(p) or {}, nq.get(p) or {}
        if a.get("format") != "csv" and b.get("format") != "csv":
            continue
        ac = [c["name"] for c in a.get("columns") or []]
        bc = [c["name"] for c in b.get("columns") or []]
        tables.append({"path": p, "rows_before": a.get("rows"), "rows_after": b.get("rows"),
                       "columns_added": [c for c in bc if c not in ac],
                       "columns_removed": [c for c in ac if c not in bc]})

    def _checks(m):
        return {(c["name"], c["target"]): c["passed"] for c in (m.get("quality") or {}).get("checks") or []}
    oc, nc = _checks(old), _checks(new)
    check_changes = [{"check": k[0], "target": k[1], "before": oc.get(k), "after": nc.get(k)}
                     for k in sorted(set(oc) | set(nc)) if oc.get(k) != nc.get(k)]

    def _runs(m):
        return (m.get("lineage") or {}).get("collection_runs") or []
    seen = {(r.get("started_at"), r.get("agent")) for r in _runs(old)}
    new_runs = [r for r in _runs(new) if (r.get("started_at"), r.get("agent")) not in seen]

    oref, nref = old.get("reference") or {}, new.get("reference") or {}
    ref_changes = {k: {"before": oref.get(k), "after": nref.get(k)}
                   for k in sorted(set(oref) | set(nref))
                   if oref.get(k) != nref.get(k) and k not in ("updated_at", "last_collected_at")}

    return {"dataset_id": new["dataset_id"],
            "version_before": old["version"], "version_after": new["version"],
            "created_before": old["created_at"], "created_after": new["created_at"],
            "files": files, "tables": tables, "check_changes": check_changes,
            "new_collection_runs": new_runs, "reference_changes": ref_changes,
            "identical_content": not files["added"] and not files["removed"] and not files["changed"]}


def diff_packages(old_path: Path, new_path: Path, key: Optional[str] = None,
                  pubkey_pem: Optional[bytes] = None) -> Dict[str, Any]:
    return diff_manifests(_load(old_path, key, pubkey_pem), _load(new_path, key, pubkey_pem))

