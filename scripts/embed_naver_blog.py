"""
meta_naver_blog_vec 테이블에 임베딩을 생성하여 삽입하는 스크립트.

실행 방법:
    pip install sentence-transformers psycopg2-binary pgvector
    python scripts/embed_naver_blog.py

환경변수:
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
    (없으면 .env 파일 또는 기본값 사용)
"""

import os
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
    """임베딩 입력 텍스트 구성: title + description (+ content 앞 500자).

    형식은 meta_naver_blog_vec.sql의 embed_text 컬럼 설명과 일치시킨다.
    has_content=FALSE(본문 스크래핑 실패)인 게시물은 title + description만 사용.
    """
    title = row.get("title") or ""
    description = row.get("description") or ""
    parts = [title, description]
    if row.get("has_content"):
        content = row.get("content") or ""
        parts.append(content[:500])
    return ". ".join(p for p in parts if p)


def main():
    from sentence_transformers import SentenceTransformer

    model_name = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    print(f"모델 로딩: {model_name}")
    model = SentenceTransformer(model_name)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, description, content, has_content
        FROM meta_naver_blog
    """)
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    posts = [dict(zip(columns, row)) for row in rows]
    print(f"대상 게시물: {len(posts)}건")

    # DELETE → INSERT (개발 단계: 항상 재생성)
    cur.execute("DELETE FROM meta_naver_blog_vec")
    print("기존 임베딩 삭제 완료")

    for p in posts:
        embed_text = build_embed_text(p)
        vec = model.encode(embed_text)       # shape (768,)
        vec_list = vec.tolist()

        cur.execute("""
            INSERT INTO meta_naver_blog_vec (meta_id, embedding, embed_text, model_name)
            VALUES (%s, %s::vector, %s, %s)
        """, (p["id"], str(vec_list), embed_text, model_name))

        print(f"  [meta_id={p['id']}] {p['title'][:40]!r} 임베딩 완료 — dim={len(vec_list)}")

    conn.commit()
    cur.close()
    conn.close()
    print("모든 임베딩 삽입 완료.")


if __name__ == "__main__":
    main()
