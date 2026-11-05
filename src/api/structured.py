"""정형 1st party 업로드 + 전 기관 수집 오류 조회 (D1).

## 정형 1st party 업로드 — 우리 몫과 와이즈넛 몫의 경계

정형 데이터 중 기관이 **직접 보유한(1st party)** 것은 포털에서 올린다.
**메타데이터(JSON) + 원본 파일**을 함께 받는다.

    포털 업로드  ──▶  오브젝트 스토리지 raw/structured/upload/{해시}/   ← 여기(모비젠)
                ──▶  dcat_dataset_draft (status=PENDING)               ← 여기(모비젠)
                ──▶  표준 매핑·파싱 → dcat_dataset 등재                 ← 와이즈넛 알고리즘

`dcat_dataset_draft`는 와이즈넛 설계 초안 v2의 "표준 매핑 초안 + 매핑 증거, 원본 스냅샷
참조를 겸한다" 테이블이다. 여기서는 **매핑하지 않는다** — 받은 메타데이터를 손대지 않고
`content`에 그대로 두고, 매핑은 와이즈넛 알고리즘이 `mapping_evidence`와 함께 채운다.
같은 것을 두 곳에서 해석하면 결과가 갈린다.

- `payload_sha256`이 UNIQUE라 **같은 메타데이터+파일 조합의 재업로드를 DB가 막는다**
- 비정형에는 1st party가 없다 — 전부 외부 원천에서 수집한다(`party='3rd'`)

## 전 기관 수집 오류

관리자는 기관·원천과 상관없이 **실패한 것 전부**를 한곳에서 봐야 한다. 정형(와이즈넛)도
같은 `data_registry`·`dcat_provenance`를 쓰므로(설계 초안 §4.3 자동 실행 계약) 들어오는 대로
여기 함께 나온다.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from src.common import config
from src.database.db import get_conn

router = APIRouter(prefix="/v1/console", tags=["정형 업로드·오류"])

#: 업로드 한 건 상한. 원본 파일을 메모리로 받으므로 무한정 받지 않는다.
MAX_TOTAL_BYTES = 500 * 1024 * 1024
MAX_FILES = 50

#: 초안의 출처 표기 — 포털 직접 업로드(1st party)
SOURCE = "PORTAL_UPLOAD"

#: 아직 아무도 매핑하지 않았다는 표시. 와이즈넛 알고리즘이 자기 버전으로 바꾼다
UNMAPPED = "unmapped"


def _rows(cur) -> List[Dict[str, Any]]:
    names = [c[0] for c in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


@router.post("/structured/uploads")
async def upload_structured(metadata: UploadFile = File(..., description="메타데이터 JSON"),
                            files: List[UploadFile] = File(..., description="원본 데이터 파일"),
                            note: str = Form("")):
    """정형 1st party 데이터 업로드 — 초안으로 받고 매핑은 와이즈넛 알고리즘에 넘긴다."""
    raw_meta = await metadata.read()
    try:
        meta = json.loads(raw_meta.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise HTTPException(400, f"메타데이터가 JSON이 아니다: {e}")
    if not isinstance(meta, dict):
        raise HTTPException(400, "메타데이터 JSON의 최상위는 객체({ … })여야 한다")
    if not files or not any(f.filename for f in files):
        raise HTTPException(400, "원본 데이터 파일을 1개 이상 올려야 한다")
    if len(files) > MAX_FILES:
        raise HTTPException(400, f"파일은 {MAX_FILES}개까지다")

    blobs, total = [], len(raw_meta)
    for f in files:
        data = await f.read()
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise HTTPException(413, f"한 번에 {MAX_TOTAL_BYTES // 1024 // 1024}MB까지 올릴 수 있다")
        name = (f.filename or "file").replace("/", "_").replace("\\", "_")
        blobs.append((name, data, f.content_type or "application/octet-stream"))

    # 메타데이터 + 파일(이름순)의 해시 — 같은 조합이면 같은 값이 나와 UNIQUE에 걸린다
    h = hashlib.sha256(raw_meta)
    for name, data, _ in sorted(blobs, key=lambda b: b[0]):
        h.update(name.encode()); h.update(hashlib.sha256(data).digest())
    digest = h.hexdigest()

    cur = get_conn().cursor()
    cur.execute("SELECT id, status FROM dcat_dataset_draft WHERE payload_sha256=%s", (digest,))
    dup = cur.fetchone()
    if dup:
        raise HTTPException(409, f"같은 메타데이터·파일 조합이 이미 올라와 있다 (초안 #{dup[0]}, {dup[1]})")

    from src.storage import s3_client
    prefix = f"raw/structured/upload/{digest[:16]}/"
    uploaded = []
    try:
        s3_client.upload_bytes(prefix + "metadata.json", raw_meta, "application/json")
        for name, data, ctype in blobs:
            s3_client.upload_bytes(prefix + "files/" + name, data, ctype)
            uploaded.append({"name": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                             "key": prefix + "files/" + name, "content_type": ctype})
    except Exception as e:                        # noqa: BLE001
        try:
            s3_client.delete_upload_prefix(prefix)
        except Exception:                         # noqa: BLE001
            pass
        raise HTTPException(502, config.mask_secrets(f"원본을 저장하지 못했다: {e}")[:300])

    evidence = {"party": "1st", "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "uploaded_by": "총괄 관리자", "note": note[:500], "metadata_key": prefix + "metadata.json",
                "files": uploaded}
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""INSERT INTO dcat_dataset_draft
                   (source, payload_sha256, raw_storage_key, mapping_version, status, content, mapping_evidence)
                   VALUES (%s, %s, %s, %s, 'PENDING', %s::jsonb, %s::jsonb) RETURNING id""",
                (SOURCE, digest, prefix, UNMAPPED, json.dumps(meta, ensure_ascii=False),
                 json.dumps(evidence, ensure_ascii=False)))
    draft_id = cur.fetchone()[0]
    conn.commit()
    return {"draft_id": draft_id, "status": "PENDING", "raw_storage_key": prefix, "files": len(uploaded),
            "note": "올라갔다. 메타데이터 파싱·표준 매핑은 와이즈넛 알고리즘이 한다(매핑 대기)"}


@router.get("/structured/uploads")
def list_uploads(limit: int = 100):
    cur = get_conn().cursor()
    cur.execute("""SELECT id, source, status, mapping_version, raw_storage_key, auto_threshold,
                          reviewed_by, reviewed_at, created_at,
                          content->>'title' AS title, content->>'publisher' AS publisher,
                          jsonb_array_length(coalesce(mapping_evidence->'files','[]'::jsonb)) AS file_count,
                          mapping_evidence->>'party' AS party
                   FROM dcat_dataset_draft ORDER BY created_at DESC LIMIT %s""", (limit,))
    return {"items": _rows(cur)}


@router.get("/structured/uploads/{draft_id}")
def get_upload(draft_id: int):
    cur = get_conn().cursor()
    cur.execute("SELECT * FROM dcat_dataset_draft WHERE id=%s", (draft_id,))
    rows = _rows(cur)
    if not rows:
        raise HTTPException(404, "그런 업로드가 없다")
    return rows[0]


@router.delete("/structured/uploads/{draft_id}")
def cancel_upload(draft_id: int):
    """매핑 전(PENDING)에만 취소할 수 있다. 와이즈넛이 집어 간 뒤에는 그쪽 흐름을 깬다."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT status, raw_storage_key, source FROM dcat_dataset_draft WHERE id=%s", (draft_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "그런 업로드가 없다")
    if row[0] != "PENDING" or row[2] != SOURCE:
        raise HTTPException(409, f"매핑 대기(PENDING)인 포털 업로드만 취소할 수 있다 (지금 {row[0]})")
    cur.execute("DELETE FROM dcat_dataset_draft WHERE id=%s", (draft_id,))
    conn.commit()
    from src.storage import s3_client
    removed = s3_client.delete_upload_prefix(row[1])
    return {"draft_id": draft_id, "cancelled": True, "objects_removed": removed}


# ── 전 기관 수집 오류 ─────────────────────────────────────────────────────

@router.get("/errors")
def errors(days: int = 30):
    """기관·원천과 상관없이 **실패한 것 전부**. 관리자가 매일 여는 화면이다."""
    cur = get_conn().cursor()
    org = ("d.title, d.publisher, d.source, d.source_type, d.dataset_origin, "
           "coalesce(d.party, '') AS party")
    cur.execute(f"""SELECT p.prov_id, p.dataset_id, {org}, p.activity_type, p.triggered_by,
                           p.started_at, p.ended_at, p.status, p.error_message
                    FROM dcat_provenance p LEFT JOIN dcat_dataset d USING (dataset_id)
                    WHERE p.status <> 'success' AND p.started_at > now() - make_interval(days => %s)
                    ORDER BY p.started_at DESC LIMIT 300""", (days,))
    failed_runs = _rows(cur)
    cur.execute(f"""SELECT r.dataset_id, {org}, r.status, r.last_error, r.last_collected_at, r.next_collect_at
                    FROM data_registry r JOIN dcat_dataset d USING (dataset_id)
                    WHERE r.status = 'error' ORDER BY r.updated_at DESC""")
    in_error = _rows(cur)
    # 예정이 1시간 넘게 지났는데 돌지 않은 것 — 스케줄러가 멈췄거나 없다는 신호
    cur.execute(f"""SELECT r.dataset_id, {org}, r.status, r.next_collect_at, r.last_collected_at,
                           extract(epoch FROM now() - r.next_collect_at)/3600 AS hours_late
                    FROM data_registry r JOIN dcat_dataset d USING (dataset_id)
                    WHERE r.status IN ('active','pending') AND r.next_collect_at < now() - interval '1 hour'
                    ORDER BY r.next_collect_at""")
    overdue = [{**r, "hours_late": round(float(r["hours_late"]), 1)} for r in _rows(cur)]
    cur.execute("""SELECT id, source, status, content->>'title' AS title, created_at, mapping_evidence->>'error' AS error
                   FROM dcat_dataset_draft WHERE status IN ('FAILED','ERROR','REJECTED')
                   ORDER BY created_at DESC LIMIT 100""")
    drafts = _rows(cur)
    return {"days": days, "failed_runs": failed_runs, "in_error": in_error, "overdue": overdue,
            "failed_drafts": drafts,
            "counts": {"failed_runs": len(failed_runs), "in_error": len(in_error), "overdue": len(overdue),
                       "failed_drafts": len(drafts)}}
