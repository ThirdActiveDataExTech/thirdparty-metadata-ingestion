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
        host=os.getenv("DB_HOST", "localhost"),
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


if __name__ == "__main__":
    main()
