"""API 응답 모양 (C6).

**허용 목록 방식이다.** 테이블 컬럼을 그대로 흘려보내지 않고 여기 적은 것만 나간다.
컬럼이 늘 때마다 응답이 저절로 넓어지면, 언젠가 내보내면 안 되는 것이 섞여 나간다.

내보내지 않는 것:

| 대상 | 이유 |
|---|---|
| `dataset_credentials` 전체 | **API Key 암호문.** 어떤 경로로도 노출하지 않는다 |
| `dcat_dataset.owner_id` | 플랫폼 계정 식별자. 데이터셋 메타가 아니다 |
| `party` | 내부 권한 메타 |
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DatasetSummary(BaseModel):
    dataset_id: str
    title: str
    description: Optional[str] = None
    publisher: Optional[str] = None
    source_type: str
    source: Optional[str] = Field(None, description="원천 시스템(Naver·YouTube·CKAN 등)")
    origin: str = Field(..., description="admin · user · external")
    keywords: List[str] = []
    theme: List[str] = Field([], description="원천이 제공한 분류")
    category: List[str] = Field([], description="공통 분류 76종. 사람이 확정한 값(ADR-020)")
    item_count: Optional[int] = None
    temporal_start: Optional[date] = None
    temporal_end: Optional[date] = None
    license: Optional[str] = None
    landing_page: Optional[str] = None
    external_ids: List[str] = []
    updated_at: Optional[datetime] = None


class DatasetDetail(DatasetSummary):
    accrual_periodicity: Optional[str] = None
    language: Optional[str] = None
    spatial: Optional[str] = None
    rights: Optional[str] = None
    features: Dict[str, Any] = Field({}, description="B1 특징 메타(meta_feature)")
    relations: List[Dict[str, Any]] = Field([], description="연관 데이터셋(B2) 상위")
    downloads: Dict[str, str] = Field({}, description="내려받을 수 있는 형식별 경로")


class SearchHit(BaseModel):
    id: str
    title: str
    subtitle: Optional[str] = None
    source: str = Field(..., description="video · news · blog · dataset")
    rrf: Optional[float] = Field(None, description="두 채널 결합 점수")
    vec_rank: Optional[int] = Field(None, description="벡터 채널 순위. None이면 미검출")
    kw_rank: Optional[int] = Field(None, description="키워드 채널 순위. None이면 미검출")
    ai_summary: Optional[str] = Field(None, description="추출 요약(A2). 영상만")
    ai_keywords: List[str] = []


class SearchResponse(BaseModel):
    query: str
    source: str
    tokens: List[str] = Field([], description="질의를 형태소로 끊은 결과(ADR-010)")
    rarest_token: Optional[Dict[str, Any]] = Field(
        None, description="최희귀어와 문서빈도. absent=true면 답이 없을 가능성이 높다(ADR-018)")
    total: int
    hits: List[SearchHit] = []


class Page(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[DatasetSummary] = []
