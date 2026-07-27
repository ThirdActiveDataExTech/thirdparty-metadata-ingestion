"""신규 데이터셋 등록 헬퍼 (관리자/개발용 CLI).

runbooks/04_Add_New_Dataset_Existing_Source.md의 "A. 신규 데이터셋 생성" 절차를
그대로 구현한다. §6.3(프론트엔드 등록 API)와 Airflow가 아직 없어서, 지금은 이
스크립트로 dcat_dataset/data_registry(+선언형이면 meta_naver_shopping/persona)를
채우고 `python -m src.main run <dataset_id>`로 수동 트리거하는 게 실질적인
등록~수집 경로다.

사용 예:
  # 발견형 (YouTube) — 다른 채널을 새 데이터셋으로
  python scripts/register_dataset.py video \\
      --title "SK하이닉스 공식 채널" --description "SK하이닉스 유튜브 채널 영상 수집" \\
      --subjects UCltyil2FaQZZ4kUNinKkKmw --origin admin

  # 선언형 (쇼핑인사이트) — 다른 카테고리 조합을 새 데이터셋으로, 소급 수집 시작일 지정
  python scripts/register_dataset.py shopping_insight \\
      --title "IT/가전 카테고리 쇼핑 인사이트" --description "..." \\
      --categories "50000003:디지털/가전,50000005:가구/인테리어" --origin admin \\
      --temporal-start 2025-01-01

등록 후 실제 수집을 트리거하려면:
  python -m src.main run <출력된-dataset_id>
"""

import argparse
import json
import re
import secrets

from src.database.db import get_conn

DISCOVERY_TYPES = {"video", "news", "blog"}
DECLARATIVE_TYPES = {"shopping_insight", "persona_insight"}

_SOURCE_META = {
    "video": {
        "publisher": "YouTube",
        "pg_meta_table": "meta_youtube_video",
        "pg_active_table": "active_meta_youtube",
        "license": "https://developers.google.com/youtube/terms/api-services-tos",
    },
    "news": {
        "publisher": "Naver",
        "pg_meta_table": "meta_naver_news",
        "pg_active_table": "active_meta_naver_news",
        "license": "https://developers.naver.com/notice/terms",
    },
    "blog": {
        "publisher": "Naver",
        "pg_meta_table": "meta_naver_blog",
        "pg_active_table": "active_meta_naver_blog",
        "license": "https://developers.naver.com/notice/terms",
    },
    "shopping_insight": {
        "publisher": "Naver",
        "pg_meta_table": "meta_naver_shopping",
        "pg_active_table": "active_meta_naver_shopping",
        "license": "https://developers.naver.com/notice/terms",
    },
    "persona_insight": {
        "publisher": "Naver",
        "pg_meta_table": "meta_naver_persona",
        "pg_active_table": "active_meta_naver_persona",
        "license": "https://developers.naver.com/notice/terms",
    },
}


def slugify(title: str) -> str:
    """영문/숫자만 남기고 슬러그화 — 한글 제목이면 거의 다 걸러져 'dataset'으로
    폴백하니, 그럴 땐 --dataset-id로 직접 영문 slug를 지정하는 걸 권장한다."""
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return slug or "dataset"


def make_dataset_id(conn, title: str, origin: str) -> str:
    """slug + 랜덤 접미사. unique_violation 시 재시도 (§7.1)."""
    base = slugify(title)
    prefix = "user_" if origin == "user" else ""
    cur = conn.cursor()
    for _ in range(5):
        candidate = f"{prefix}{base}_{secrets.token_hex(3)}"
        cur.execute("SELECT 1 FROM dcat_dataset WHERE dataset_id = %s", (candidate,))
        if cur.fetchone() is None:
            return candidate
    raise RuntimeError("dataset_id 채번 5회 시도 후에도 충돌 — 다시 시도해주세요")


def register_discovery(args) -> str:
    meta = _SOURCE_META[args.source_type]
    subjects = args.subjects.split(",")

    conn = get_conn()
    try:
        dataset_id = args.dataset_id or make_dataset_id(conn, args.title, args.origin)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO dcat_dataset (
                dataset_id, title, description, publisher, source_type,
                subjects, accrual_periodicity, dataset_origin, owner_id, license
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                dataset_id, args.title, args.description, meta["publisher"],
                args.source_type, json.dumps(subjects), args.periodicity,
                args.origin, args.owner_id, meta["license"],
            ),
        )
        cur.execute(
            """
            INSERT INTO data_registry (
                dataset_id, status, next_collect_at,
                pg_meta_table, pg_active_table, vec_collection
            ) VALUES (%s, 'pending', now(), %s, %s, 'dcat_dataset_vec')
            """,
            (dataset_id, meta["pg_meta_table"], meta["pg_active_table"]),
        )
        conn.commit()
        return dataset_id
    finally:
        conn.close()


def register_declarative(args) -> str:
    meta = _SOURCE_META[args.source_type]
    categories = []
    for item in args.categories.split(","):
        cat_id, _, cat_name = item.partition(":")
        if not cat_id or not cat_name:
            raise ValueError(f"--categories 형식 오류: {item!r} (기대: 'id:name')")
        categories.append((cat_id.strip(), cat_name.strip()))

    conn = get_conn()
    try:
        dataset_id = args.dataset_id or make_dataset_id(conn, args.title, args.origin)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO dcat_dataset (
                dataset_id, title, description, publisher, source_type,
                subjects, accrual_periodicity, item_count,
                dataset_origin, owner_id, license, temporal_start
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                dataset_id, args.title, args.description, meta["publisher"],
                args.source_type, json.dumps([cid for cid, _ in categories]), args.periodicity,
                len(categories), args.origin, args.owner_id, meta["license"], args.temporal_start,
            ),
        )
        cur.execute(
            """
            INSERT INTO data_registry (
                dataset_id, status, next_collect_at,
                pg_meta_table, pg_active_table, vec_collection, item_count
            ) VALUES (%s, 'pending', now(), %s, %s, 'dcat_dataset_vec', %s)
            """,
            (dataset_id, meta["pg_meta_table"], meta["pg_active_table"], len(categories)),
        )

        # 첫 번째로 고른 카테고리를 자동으로 anchor 지정 (§4.3, shopping만 해당 컬럼 있음)
        table = meta["pg_meta_table"]
        for i, (cat_id, cat_name) in enumerate(categories):
            if table == "meta_naver_shopping":
                cur.execute(
                    """
                    INSERT INTO meta_naver_shopping
                        (dataset_id, category_id, category_name, is_anchor)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (dataset_id, cat_id, cat_name, i == 0),
                )
            else:  # meta_naver_persona — anchor 개념 없음
                cur.execute(
                    """
                    INSERT INTO meta_naver_persona (dataset_id, category_id, category_name)
                    VALUES (%s, %s, %s)
                    """,
                    (dataset_id, cat_id, cat_name),
                )
        conn.commit()
        return dataset_id
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source_type", choices=sorted(DISCOVERY_TYPES | DECLARATIVE_TYPES))
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--origin", choices=["admin", "user"], default="admin")
    parser.add_argument("--owner-id", default=None, help="origin=user일 때만 의미 있음")
    parser.add_argument("--periodicity", default="P1D", help="ISO 8601 duration, 기본 P1D")
    parser.add_argument("--dataset-id", default=None, help="지정 안 하면 title로 자동 채번")
    parser.add_argument("--subjects", help="발견형: 채널ID/검색어 콤마 구분 목록")
    parser.add_argument("--categories", help="선언형: 'id:name,id:name' 콤마 구분 목록")
    parser.add_argument(
        "--temporal-start", default=None, metavar="YYYY-MM-DD",
        help="선언형(shopping_insight/persona_insight) 전용: 최초 수집 시 이 날짜부터 "
             "소급 수집한다(naver_shopping_pipeline.py 참조). 발견형은 아직 안 씀.",
    )
    args = parser.parse_args()

    if args.source_type in DISCOVERY_TYPES:
        if not args.subjects:
            parser.error(f"source_type={args.source_type!r}는 --subjects 필요")
        dataset_id = register_discovery(args)
    else:
        if not args.categories:
            parser.error(f"source_type={args.source_type!r}는 --categories 필요")
        dataset_id = register_declarative(args)

    print(f"등록 완료: {dataset_id}")
    print(f"수집 트리거: python -m src.main run {dataset_id}")


if __name__ == "__main__":
    main()
