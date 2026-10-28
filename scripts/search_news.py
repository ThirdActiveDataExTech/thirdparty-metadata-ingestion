"""
자연어 질의로 유사한 Naver 뉴스 기사를 검색하는 테스트 스크립트.

실행 방법:
    python scripts/search_news.py "HBM4 관련 최신 기사"

환경변수:
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
"""

import sys
import os
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


def search(query: str, top_k: int = 3):
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
    q_vec = model.encode(query).tolist()

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT m.id,
               m.title,
               m.publisher,
               ROUND((1 - (v.embedding <=> %s::vector))::numeric, 4) AS similarity
        FROM meta_news_vec v
        JOIN meta_news m ON m.id = v.meta_id
        ORDER BY v.embedding <=> %s::vector
        LIMIT %s
    """, (str(q_vec), str(q_vec), top_k))

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "HBM4 반도체 관련 최신 기사"
    print(f"\n질의: {query}\n")
    results = search(query)
    for i, (meta_id, title, publisher, sim) in enumerate(results, 1):
        print(f"{i}. [{sim}] meta_id={meta_id}")
        print(f"   제목: {title}")
        print(f"   언론사: {publisher}")
        print()
