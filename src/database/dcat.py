"""dcat_dataset / dcat_provenance / data_registry / dataset_credentials 공통 헬퍼.

모든 소스 타입의 pipeline이 공유하는 "수집 실행 이력 남기기 + 운영 상태 갱신 +
API 키 조회" 로직. architecture/04_Collection_Pipeline_Operations.md §6.1/§9 참조.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from src.common import config
from src.database.db import get_conn

# credential_type -> 플랫폼 공유 키로 쓸 환경변수 이름 (dataset_credentials에 없을 때 폴백)
_PLATFORM_KEY_ENV = {
    "youtube_api_key": "YOUTUBE_API_KEY",
    "naver_client_id": "NAVER_CLIENT_ID",
    "naver_client_secret": "NAVER_CLIENT_SECRET",
}

# data_registry.UPDATE에서 허용하는 컬럼만 화이트리스트로 관리 (동적 SQL이라도
# 임의 컬럼명이 섞여 들어가지 않도록)
_DATA_REGISTRY_COLUMNS = {
    "status",
    "last_collected_at",
    "next_collect_at",
    "last_error",
    "item_count",
    "row_count",
    "temporal_start",
    "temporal_end",
    "pg_meta_table",
    "pg_active_table",
    "vec_collection",
    "s3_raw_prefix",
    "s3_jsonld_prefix",
}

# dcat_dataset.UPDATE에서 허용하는 컬럼 화이트리스트
_DCAT_DATASET_COLUMNS = {
    "temporal_start",
    "temporal_end",
    "item_count",
}


def fetch_dcat_dataset(dataset_id: str) -> Dict[str, Any]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT dataset_id, title, description, publisher, source_type,
                   subjects, accrual_periodicity, dataset_origin, owner_id,
                   temporal_start, temporal_end
            FROM dcat_dataset WHERE dataset_id = %s
            """,
            (dataset_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"dcat_dataset에 dataset_id={dataset_id!r} 없음")
        columns = [d[0] for d in cur.description]
        return dict(zip(columns, row))
    finally:
        conn.close()


def update_dcat_dataset(dataset_id: str, **fields: Any) -> None:
    """전달된 필드만 UPDATE. updated_at은 항상 now()로 같이 갱신."""
    unknown = set(fields) - _DCAT_DATASET_COLUMNS
    if unknown:
        raise ValueError(f"dcat_dataset UPDATE에 없는 컬럼: {unknown}")
    if not fields:
        return

    set_clause = ", ".join(f"{col} = %s" for col in fields)
    values = list(fields.values()) + [dataset_id]

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE dcat_dataset SET {set_clause}, updated_at = now() WHERE dataset_id = %s",
            values,
        )
        conn.commit()
    finally:
        conn.close()


def insert_dcat_provenance(
    dataset_id: str,
    activity_type: str,
    agent: str,
    triggered_by: str,
    started_at: datetime,
    ended_at: Optional[datetime] = None,
    status: str = "running",
    rows_affected: Optional[int] = None,
    params: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    notes: Optional[str] = None,
) -> None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO dcat_provenance
                (dataset_id, activity_type, agent, triggered_by,
                 started_at, ended_at, status, rows_affected, params,
                 error_message, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                dataset_id, activity_type, agent, triggered_by,
                started_at, ended_at, status, rows_affected,
                json.dumps(params) if params is not None else None,
                error_message, notes,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def update_data_registry(dataset_id: str, **fields: Any) -> None:
    """전달된 필드만 UPDATE. updated_at은 항상 now()로 같이 갱신."""
    unknown = set(fields) - _DATA_REGISTRY_COLUMNS
    if unknown:
        raise ValueError(f"data_registry에 없는 컬럼: {unknown}")
    if not fields:
        return

    set_clause = ", ".join(f"{col} = %s" for col in fields)
    values = list(fields.values()) + [dataset_id]

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE data_registry SET {set_clause}, updated_at = now() "
            f"WHERE dataset_id = %s",
            values,
        )
        conn.commit()
    finally:
        conn.close()


def get_api_key(dataset_id: str, credential_type: str) -> Optional[str]:
    """dataset_credentials에서 우선 조회, 없으면 플랫폼 공유 키로 폴백.

    ENCRYPTION_KEY가 .env에 없으면(K8s Secret 미생성 상태) dataset_credentials
    조회 자체를 건너뛰고 바로 플랫폼 키로 폴백한다 — 에러를 내지 않는다.
    """
    enc_key = config.get_env("ENCRYPTION_KEY")
    if enc_key:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT pgp_sym_decrypt(encrypted_value, %s)
                FROM dataset_credentials
                WHERE dataset_id = %s AND credential_type = %s
                """,
                (enc_key, dataset_id, credential_type),
            )
            row = cur.fetchone()
            if row is not None:
                return row[0]
        finally:
            conn.close()

    env_name = _PLATFORM_KEY_ENV.get(credential_type)
    if env_name is None:
        raise ValueError(f"알 수 없는 credential_type: {credential_type}")
    return config.get_env(env_name)


def parse_iso8601_duration_to_timedelta(duration: str) -> timedelta:
    """dcat_dataset.accrual_periodicity(예: 'P1D', 'P7D')를 timedelta로 변환.

    이 프로젝트에서 실제 쓰이는 값이 P{n}D 형태뿐이라 그 범위만 지원한다.
    """
    if not duration.startswith("P") or not duration.endswith("D"):
        raise ValueError(f"지원하지 않는 accrual_periodicity 형식: {duration!r}")
    days = int(duration[1:-1])
    return timedelta(days=days)
