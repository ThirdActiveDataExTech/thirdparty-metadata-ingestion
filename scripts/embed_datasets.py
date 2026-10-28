"""
dcat_dataset_vec 테이블에 임베딩을 생성하여 삽입하는 스크립트.

실행 방법:
    pip install sentence-transformers psycopg2-binary pgvector
    python scripts/embed_datasets.py

환경변수:
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
    (없으면 .env 파일 또는 기본값 사용)
"""

import os
import json
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_conn():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=int(os.getenv("DB_PORT", 30433)),
        dbname=os.getenv("DB_NAME", "datagokr"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


def build_embed_text(row: dict) -> str:
    """임베딩 입력 텍스트 구성: title + description + keywords."""
    title = row.get("title") or ""
    description = row.get("description") or ""
    keywords = row.get("keywords") or []
    if isinstance(keywords, str):
        keywords = json.loads(keywords)
    kw_str = ", ".join(keywords) if keywords else ""
    parts = [p for p in [title, description, f"키워드: {kw_str}" if kw_str else ""] if p]
    return ". ".join(parts)


def main():
    from sentence_transformers import SentenceTransformer

    model_name = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    print(f"모델 로딩: {model_name}")
    model = SentenceTransformer(model_name)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT dataset_id, title, description, keywords
        FROM dcat_dataset
    """)
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    datasets = [dict(zip(columns, row)) for row in rows]
    print(f"대상 데이터셋: {len(datasets)}건")

    # DROP → INSERT (개발 단계: 항상 재생성)
    cur.execute("DELETE FROM dcat_dataset_vec")
    print("기존 임베딩 삭제 완료")

    for ds in datasets:
        embed_text = build_embed_text(ds)
        vec = model.encode(embed_text)       # shape (768,)
        vec_list = vec.tolist()

        cur.execute("""
            INSERT INTO dcat_dataset_vec (dataset_id, embedding, embed_text, model_name)
            VALUES (%s, %s::vector, %s, %s)
        """, (ds["dataset_id"], str(vec_list), embed_text, model_name))

        print(f"  [{ds['dataset_id']}] 임베딩 완료 — dim={len(vec_list)}")

    conn.commit()
    cur.close()
    conn.close()
    print("모든 임베딩 삽입 완료.")


# ─────────────────────────────────────────────────────────────────────────────
# ⚠️ 이 스크립트는 2026-10-28부터 사용하지 않는다.
#
# 임베딩은 수집 파이프라인이 자동으로 동기화한다(src/embedding/sync.py).
# 기존 데이터를 따라잡으려면 scripts/backfill_embeddings.py를 쓴다.
#
# 이 스크립트는 실행하면 `DELETE FROM dcat_dataset_vec` 로 **기존 임베딩을 전부 지우고**
# 1건씩 다시 만든다. 지금은 파이프라인이 채워 둔 것을 통째로 날리는 동작이라
# 실수로 돌지 않도록 막아 둔다. 구현을 참고할 일이 있어 파일은 남긴다.
#
# 그래도 돌려야 한다면 --force 를 준다.
# ─────────────────────────────────────────────────────────────────────────────
def _deprecated_guard():
    import sys
    if "--force" in sys.argv:
        return
    sys.exit(
        "이 스크립트는 더 이상 쓰지 않습니다.\n"
        "  임베딩은 수집 파이프라인이 자동 동기화합니다(src/embedding/sync.py).\n"
        "  기존 데이터 일괄 생성: PYTHONPATH=. python scripts/backfill_embeddings.py\n"
        "\n"
        "  이 스크립트를 그대로 돌리면 dcat_dataset_vec 의 기존 임베딩이 전부 삭제됩니다.\n"
        "  그래도 필요하면 --force 를 붙이세요."
    )


if __name__ == "__main__":
    _deprecated_guard()
    main()
