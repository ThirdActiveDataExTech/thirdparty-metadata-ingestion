"""특징을 뽑을 대상이 어디에 있는지 — 원천별 테이블 지도.

`src/embedding/sync.py`의 `_SPECS`와 같은 역할이지만 보는 각도가 다르다.
sync는 "무엇을 임베딩할 텍스트로 만들까"를, 여기는 "이 데이터셋의 아이템과
토큰이 어디 있나"를 본다.
"""

from typing import Dict, NamedTuple, Optional


class Spec(NamedTuple):
    base: str            # 아이템 테이블
    vec: Optional[str]   # 청크·토큰 테이블 (없는 원천이 있다)
    key: str             # vec 쪽이 base를 가리키는 컬럼
    base_key: str        # base의 PK
    has_content: bool    # 본문 보유 플래그가 있는가
    active: str          # 지표 시계열 테이블
    time_col: str        # 그 테이블의 관측 시점 컬럼


#: source_type → 테이블 지도.
#: shopping_insight·persona_insight는 아이템이 "카테고리"라 본문이 없다.
#: 청크 테이블도 없어서 텍스트 특징은 데이터셋 카탈로그(dcat_dataset_vec)에서만 온다.
SPECS: Dict[str, Spec] = {
    "video": Spec("meta_video", "meta_video_vec", "meta_id", "id", False,
                  "active_meta_video", "collected_at"),
    "news":  Spec("meta_news",  "meta_news_vec",  "meta_id", "id", True,
                  "active_meta_news", "collected_at"),
    "blog":  Spec("meta_blog",  "meta_blog_vec",  "meta_id", "id", True,
                  "active_meta_blog", "collected_at"),
    "shopping_insight": Spec("meta_shopping_insight", None, "", "id", False,
                             "active_meta_shopping_insight", "period"),
    "persona_insight":  Spec("meta_persona_insight",  None, "", "id", False,
                             "active_meta_persona_insight", "period"),
}

#: 어느 원천이든 데이터셋 카탈로그 텍스트는 여기 있다
CATALOG_VEC = "dcat_dataset_vec"
