"""격리 환경 수집 번들 — 현장 에이전트가 모으고, 플랫폼이 **서명을 확인한 뒤** 들인다 (A1 · 3차년도).

연구계획서 3차년도 "설치 및 확장 가능한 agent 형태의 수집 기술", "네트워크로 격리되어 있거나,
수집 프로세스가 없는 환경에서 데이터의 수집을 지원".

    [격리 현장]  에이전트: 파이프라인 스펙의 collect·normalize만 돈다(DB 없음)
                 → 번들 zip = 신뢰 패키지(C5) + `bundle` 절, 에이전트 키(Ed25519)로 서명
         │  파일로 반출(USB·망연계 등) — 네트워크가 끊겨 있어도 된다
         ▼
    [플랫폼]     반입: ① 등록된 에이전트 공개키로 서명 확인(출처) ② 체크섬(무결성)
                 ③ 같은 번들 재반입 거부 ④ **플랫폼 쪽 스펙**으로 적재·후처리·드리프트 판정 ⑤ 이력 기록

## 지키는 것

- **어디에 쓸지는 번들이 정하지 않는다.** 번들에는 파이프라인 이름만 있고, 대상 테이블·컬럼·충돌 키는
  플랫폼의 `configs/pipelines/<이름>.yaml`에서 읽는다. 번들이 테이블을 고르게 하면 서명된 번들 하나로
  아무 테이블에나 쓸 수 있다
- **신뢰하는 에이전트만.** 공개키를 `configs/agents/*.pub.pem`(또는 `AGENT_TRUSTED_KEYS_DIR`)에 둔 에이전트의
  번들만 받는다. 패키지에 든 공개키로 맞는 것(무결성)만으로는 받지 않는다
- **재반입은 거부한다.** 적재는 멱등이지만, 이력·활용 수치가 두 번 잡힌다(manifest SHA-256으로 판정)
"""

import json
import logging
import os
import random
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.packaging import builder, manifest as M, signing, verify as V

logger = logging.getLogger(__name__)

BUNDLE_KIND = "collection-bundle"
BUNDLE_VERSION = "1"
ROWS_FILE = "rows.jsonl"
RAW_SAMPLE_FILE = "raw_sample.jsonl"
RAW_SAMPLE_LIMIT = 200
AGENT_KEY_ENV = "AGENT_SIGNING_KEY"
TRUSTED_DIR_ENV = "AGENT_TRUSTED_KEYS_DIR"
DEFAULT_TRUSTED_DIR = Path("configs/agents")
PROV_AGENT = "agent_bundle"
_NAME = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


class BundleError(RuntimeError):
    """반입할 수 없다. `code`는 API 응답 코드로 쓴다."""

    def __init__(self, message: str, code: int = 400):
        super().__init__(message)
        self.code = code


# ── 에이전트 쪽 ────────────────────────────────────────────────────────────

def agent_key_from_env() -> signing.Ed25519PrivateKey:
    raw = os.getenv(AGENT_KEY_ENV, "").strip()
    if not raw:
        raise BundleError(f"에이전트 서명 키가 없습니다. 환경변수 {AGENT_KEY_ENV}를 설정하세요"
                          " (키 만들기: package_dataset.py keygen)")
    return signing.load_private_key(raw.replace("\\n", "\n"))


def _jsonl(rows: List[Dict[str, Any]]) -> str:
    return "".join(json.dumps(r, ensure_ascii=False, default=str, sort_keys=True) + "\n" for r in rows)


def collect_bundle(pipeline: str, out_path: Path, key: signing.Ed25519PrivateKey,
                   limit: Optional[int] = None, agent_id: Optional[str] = None) -> Dict[str, Any]:
    """파이프라인 스펙대로 수집·정규화해 서명된 번들을 만든다. **DB를 쓰지 않는다.**"""
    from src.collectors.adapters.file_source import adapter_from_file
    from src.pipeline_engine import runner, steps

    spec = runner.load(pipeline)
    adapter = adapter_from_file(spec["source_spec"])
    raws = steps.collect(adapter, query=spec.get("query"), limit=limit or spec.get("limit"))
    rows = steps.normalize(adapter, raws)
    keep = list(dict.fromkeys(spec["target"]["columns"]))
    rows = [{c: r.get(c) for c in keep} for r in rows]
    # 원본 표본 — 플랫폼에서 원천 형식 변화(드리프트)를 판정할 재료. 순서를 고정해 재현되게 한다
    rng = random.Random(len(raws))
    sample = raws if len(raws) <= RAW_SAMPLE_LIMIT else rng.sample(raws, RAW_SAMPLE_LIMIT)

    with tempfile.TemporaryDirectory(prefix="agent-bundle-") as tmp:
        src = Path(tmp)
        (src / ROWS_FILE).write_text(_jsonl(rows), encoding="utf-8")
        (src / RAW_SAMPLE_FILE).write_text(_jsonl(sample), encoding="utf-8")
        bundle = {"kind": BUNDLE_KIND, "bundle_version": BUNDLE_VERSION, "pipeline": Path(pipeline).stem,
                  "dataset_id": spec["dataset_id"], "source": adapter.source,
                  "adapter_kind": (getattr(adapter, "spec", {}) or {}).get("kind", "rest_json"),
                  "collected_at": datetime.now(timezone.utc).isoformat(),
                  "raw_count": len(raws), "row_count": len(rows), "agent_id": agent_id or ""}
        man = builder.build_package(spec["dataset_id"], src, Path(out_path),
                                    source={"collector": adapter.source},
                                    key=None, ed25519_key=key, context={"bundle": bundle})
    logger.info("번들 생성: %s (%d행, 원본 표본 %d)", out_path, len(rows), len(sample))
    return man


# ── 플랫폼 쪽 ──────────────────────────────────────────────────────────────

def trusted_keys(directory: Optional[Path] = None) -> List[Tuple[str, bytes]]:
    """신뢰하는 에이전트 공개키 [(파일 이름, PEM)]."""
    d = Path(directory or os.getenv(TRUSTED_DIR_ENV) or DEFAULT_TRUSTED_DIR)
    if not d.is_dir():
        return []
    return [(p.name, p.read_bytes()) for p in sorted(d.glob("*.pub.pem"))]


def _verify_trusted(path: Path, keys: List[Tuple[str, bytes]]) -> Tuple[V.VerifyResult, str]:
    if not keys:
        raise BundleError("등록된 에이전트 공개키가 없습니다(configs/agents/*.pub.pem)", 403)
    last = None
    for name, pem in keys:
        r = V.verify_package(path, pubkey_pem=pem)
        if r.signature_ok and r.signer_trusted:
            if not r.ok:
                hint = " — 손상 블록은 package_dataset.py repair로 복원할 수 있습니다" if r.repairable else ""
                raise BundleError("번들 내용이 서명과 맞지 않습니다: " + "; ".join(r.problems[:3]) + hint)
            return r, name
        last = r
    if last is not None and last.manifest is None:
        raise BundleError("번들을 읽을 수 없습니다: " + "; ".join(last.problems[:3]))
    raise BundleError("등록된 에이전트의 서명이 아닙니다 — 공개키를 등록했는지 확인하세요", 403)


def _read_jsonl(z: zipfile.ZipFile, name: str) -> List[Dict[str, Any]]:
    text = z.read(f"{M.DATA_DIR}/{name}").decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def ingest_bundle(path: Path, dry_run: bool = False,
                  trusted_dir: Optional[Path] = None) -> Dict[str, Any]:
    """번들을 확인하고 적재한다. 반환: 단계별 결과. 실패하면 BundleError."""
    from src.collectors.adapters.file_source import adapter_from_file
    from src.database.db import get_conn
    from src.pipeline_engine import runner, steps

    path = Path(path)
    r, key_name = _verify_trusted(path, trusted_keys(trusted_dir))
    man = r.manifest
    b = man.get("bundle") or {}
    if b.get("kind") != BUNDLE_KIND or b.get("bundle_version") != BUNDLE_VERSION:
        raise BundleError("수집 번들이 아닙니다(bundle 절이 없거나 모르는 형식)")

    # 대상은 **플랫폼 스펙**에서 — 번들이 테이블을 고르지 않는다. 이름만 받고 경로는 받지 않는다
    name = str(b.get("pipeline") or "")
    if not _NAME.match(name):
        raise BundleError("파이프라인 이름 형식이 올바르지 않습니다")
    try:
        spec = runner.load(str(runner.PIPELINE_ROOT / f"{name}.yaml"))
    except runner.PipelineError as e:
        raise BundleError(f"플랫폼에 '{name}' 파이프라인이 없습니다") from e
    if not _NAME.match(spec["target"]["table"]):
        raise BundleError("플랫폼 파이프라인의 대상 테이블 이름이 올바르지 않습니다")
    if spec["dataset_id"] != b.get("dataset_id") or man["dataset_id"] != spec["dataset_id"]:
        raise BundleError("번들의 데이터셋이 플랫폼 파이프라인의 데이터셋과 다릅니다")

    bundle_sha = M.manifest_sha256(man)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT prov_id FROM dcat_provenance WHERE agent = %s AND params->>'bundle_sha256' = %s LIMIT 1",
                (PROV_AGENT, bundle_sha))
    if cur.fetchone():
        conn.rollback()
        raise BundleError("이미 반입한 번들입니다", 409)
    conn.rollback()

    with zipfile.ZipFile(path) as z:
        rows = _read_jsonl(z, ROWS_FILE)
        sample = _read_jsonl(z, RAW_SAMPLE_FILE)
    if len(rows) != b.get("row_count"):
        raise BundleError("번들의 행 수가 기록과 다릅니다")

    target = spec["target"]
    started = datetime.now(timezone.utc)
    adapter = adapter_from_file(spec["source_spec"])
    result: Dict[str, Any] = {"dataset_id": spec["dataset_id"], "pipeline": b["pipeline"], "dry_run": dry_run,
                              "signer": key_name, "signer_fingerprint": r.signer_fingerprint,
                              "collected_at": b.get("collected_at"), "rows": len(rows), "bundle_sha256": bundle_sha}
    result["drift"] = runner._check_drift(spec["dataset_id"], sample, adapter, dry_run)
    result["store"] = steps.store(rows, spec["dataset_id"], target["table"], target["columns"],
                                  target["conflict_key"], target.get("defaults"), dry_run=dry_run)
    result["postprocess"] = steps.postprocess(spec["dataset_id"], spec.get("source_type", ""),
                                              spec.get("postprocess", []), dry_run=dry_run)
    if dry_run:
        return result

    params = {"bundle_sha256": bundle_sha, "pipeline": b["pipeline"], "agent_id": b.get("agent_id"),
              "collected_at": b.get("collected_at"), "signer": key_name,
              "signer_fingerprint": r.signer_fingerprint, "raw_count": b.get("raw_count")}
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO dcat_provenance (dataset_id, activity_type, agent, triggered_by, started_at, ended_at, "
        "status, rows_affected, params, notes) VALUES (%s, 'update', %s, %s, %s, now(), 'success', %s, %s::jsonb, %s)",
        (spec["dataset_id"], PROV_AGENT, f"agent:{key_name}", started, result["store"].get("stored", 0),
         json.dumps(params, ensure_ascii=False), "격리 환경 수집 번들 반입"))
    cur.execute("SELECT count(*) FROM " + target["table"] + " WHERE dataset_id = %s", (spec["dataset_id"],))
    count = cur.fetchone()[0]
    conn.commit()
    try:
        from src.database import dcat
        dcat.update_data_registry(spec["dataset_id"], last_collected_at=b.get("collected_at"), item_count=count)
    except Exception as e:                        # noqa: BLE001
        logger.warning("레지스트리 갱신 실패(적재는 유효): %s", type(e).__name__)
    result["item_count"] = count
    return result
