"""meta_naver_persona / active_meta_naver_persona 읽기·쓰기 헬퍼."""

from typing import Any, Dict, List, Tuple

from src.database.db import get_conn


def get_meta_naver_persona_rows(dataset_id: str) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, category_id, category_name FROM meta_naver_persona WHERE dataset_id = %s",
            (dataset_id,),
        )
        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def get_existing_gender_ratios(meta_id: int, periods: List[str]) -> Dict[Tuple[str, str], float]:
    """{(period, gender): gender_ratio} — gender_scale(stacked inter_scale) 계산용."""
    if not periods:
        return {}
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT period, gender, gender_ratio FROM active_meta_naver_persona
            WHERE meta_id = %s AND period = ANY(%s::date[])
            """,
            (meta_id, periods),
        )
        return {(row[0].isoformat(), row[1]): row[2] for row in cur.fetchall() if row[2] is not None}
    finally:
        conn.close()


def get_existing_age_ratios(meta_id: int, periods: List[str]) -> Dict[Tuple[str, str], float]:
    """{(period, age): age_ratio} — age_scale(stacked inter_scale) 계산용."""
    if not periods:
        return {}
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT period, age, age_ratio FROM active_meta_naver_persona
            WHERE meta_id = %s AND period = ANY(%s::date[])
            """,
            (meta_id, periods),
        )
        return {(row[0].isoformat(), row[1]): row[2] for row in cur.fetchall() if row[2] is not None}
    finally:
        conn.close()


def upsert_active_meta_naver_persona(
    meta_id: int,
    period: str,
    gender: str,
    age: str,
    gender_ratio,
    age_ratio,
    gender_scale: float,
    age_scale: float,
    gender_pv,
    age_pv,
    persona_index,
) -> None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO active_meta_naver_persona
                (meta_id, period, gender, age, gender_ratio, age_ratio,
                 gender_scale, age_scale, gender_pv, age_pv, persona_index)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (meta_id, period, gender, age) DO UPDATE SET
                gender_ratio = EXCLUDED.gender_ratio,
                age_ratio = EXCLUDED.age_ratio,
                gender_scale = EXCLUDED.gender_scale,
                age_scale = EXCLUDED.age_scale,
                gender_pv = EXCLUDED.gender_pv,
                age_pv = EXCLUDED.age_pv,
                persona_index = EXCLUDED.persona_index,
                collected_at = now()
            """,
            (
                meta_id, period, gender, age, gender_ratio, age_ratio,
                gender_scale, age_scale, gender_pv, age_pv, persona_index,
            ),
        )
        conn.commit()
    finally:
        conn.close()
