"""관계 산출 결과를 `dcat_dataset_relation`에 넣는다 (B2).

**덮어쓴다, 쌓지 않는다.** 관계는 "현재 데이터 기준의 판정"이고, 데이터가
바뀌면 같은 쌍의 점수도 바뀐다. 테이블의 UNIQUE 제약
`(source, target, relation_type, method)`이 그 전제를 이미 담고 있다.

**사람이 확정한 행은 건드리지 않는다.** `status='APPROVED'`/`'REJECTED'`는
검토를 거친 값이다. 재산출이 그걸 `PENDING`으로 되돌리면 검토가 무의미해진다
(ADR-020에서 분류에 대해 내린 결정과 같은 태도).

**우리가 만든 것만 지운다.** `method='embedding'` 행만 정리 대상이다.
와이즈넛 모델 산출(`method='llm'`/`'gnn'`, B4)과 규칙 기반(`'rule'`)은
같은 테이블에 공존한다.
"""

import logging
from typing import Any, Dict, List

from psycopg2.extras import Json, execute_values

from src.analysis.relations.similarity import METHOD
from src.database.db import get_conn

logger = logging.getLogger(__name__)


def replace(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    """산출 결과로 이 방식(`method='embedding'`)의 관계를 교체한다.

    반환: {'deleted': 지운 행, 'written': 넣은 행, 'kept': 보존한 검토 완료 행}
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT count(*) FROM dcat_dataset_relation "
            "WHERE method = %s AND status <> 'PENDING'", (METHOD,))
        kept = cur.fetchone()[0]

        cur.execute(
            "DELETE FROM dcat_dataset_relation "
            "WHERE method = %s AND status = 'PENDING'", (METHOD,))
        deleted = cur.rowcount

        if not rows:
            conn.commit()
            return {"deleted": deleted, "written": 0, "kept": kept}

        payload = [
            (r["source_dataset_id"], r["target_dataset_id"], r["relation_type"],
             r["score"], r["method"], r["status"], Json(r["evidence"]))
            for r in rows
        ]
        # 검토 완료 행과 같은 쌍이 다시 산출될 수 있다 — 그 행은 건드리지 않는다
        execute_values(
            cur,
            "INSERT INTO dcat_dataset_relation "
            "  (source_dataset_id, target_dataset_id, relation_type, score, "
            "   method, status, evidence) "
            "VALUES %s "
            "ON CONFLICT (source_dataset_id, target_dataset_id, relation_type, method) "
            "DO NOTHING",
            payload, page_size=500, fetch=False)
        written = cur.rowcount
        conn.commit()
        logger.info("관계 교체: 삭제 %d · 추가 %d · 검토완료 보존 %d",
                    deleted, written, kept)
        return {"deleted": deleted, "written": written, "kept": kept}
    finally:
        conn.close()


def neighbours(dataset_id: str, relation_type: str = None, limit: int = 10):
    """이 데이터셋과 연관된 데이터셋 — B3 최소선(1-hop)이 쓰는 조회.

    상위 K가 방향을 갖고 저장되므로 단순 SELECT로 끝난다.
    """
    conn = get_conn()
    cur = conn.cursor()
    sql = """
        SELECT r.target_dataset_id, d.title, d.source_type,
               r.relation_type, r.score, r.evidence
        FROM   dcat_dataset_relation r
        JOIN   dcat_dataset d ON d.dataset_id = r.target_dataset_id
        WHERE  r.source_dataset_id = %s
          AND  r.status <> 'REJECTED'
    """
    params: List[Any] = [dataset_id]
    if relation_type:
        sql += " AND r.relation_type = %s"
        params.append(relation_type)
    sql += " ORDER BY r.score DESC LIMIT %s"
    params.append(limit)
    cur.execute(sql, params)
    names = [c[0] for c in cur.description]
    out = [dict(zip(names, r)) for r in cur.fetchall()]
    cur.close()
    return out
