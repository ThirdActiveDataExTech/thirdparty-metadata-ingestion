"""외부 반출 가능 여부 — 한 곳에서 판정한다 (NEXT_STEPS 결정 7, 2026-11-06 결정 · 2026-11-11 구현).

외부로 나가는 기능(허깅페이스 형식 내려받기, 나중의 외부 LLM 전송)은 **두 조건을 모두**
만족하는 데이터셋만 허용한다.

1. 공개 범위가 `PUBLIC`
2. 원천 라이선스가 **재배포를 허용**한다고 확인된 것

원천 약관(2026-11-06 확인)
  - 네이버 검색·데이터랩 API: "외부 배포·상업적 재판매 금지" ❌
  - YouTube API: "제3자 제공 시 Google 사전 승인" ❌
  - CKAN 캐나다(Open Government Licence - Canada): 출처 표시 조건 재배포 허용 ✅

판정은 보수적으로 한다 — **모르는 라이선스는 불가**다. 허용 목록에 넣을 때는 약관 원문을
확인하고 근거를 주석으로 남긴다. 우리 서버 안에서 쓰는 기능(로컬 sLLM 등)은 제한하지 않는다.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

#: 원천 약관상 외부 반출이 안 되는 원천(source_type). 사용자에게 보여 줄 사유.
NO_EXPORT: Dict[str, str] = {
    "video": "YouTube 약관상 제3자 제공은 Google 사전 승인이 필요합니다",
    "news": "네이버 검색 API 약관상 외부 배포·상업적 재판매가 금지됩니다",
    "blog": "네이버 검색 API 약관상 외부 배포·상업적 재판매가 금지됩니다",
    "shopping_insight": "네이버 데이터랩 약관상 외부 배포·상업적 재판매가 금지됩니다",
    "persona_insight": "네이버 데이터랩 약관상 외부 배포·상업적 재판매가 금지됩니다",
}


@dataclass(frozen=True)
class License:
    """재배포가 허용된 라이선스. `hf_id`는 허깅페이스 데이터셋 카드의 license 값."""
    name: str
    hf_id: str                       # 허깅페이스 표준 id, 목록에 없으면 "other"
    link: str
    attribution: str                 # 재배포 시 지켜야 할 조건(카드에 그대로 적는다)


#: 재배포 허용이 확인된 라이선스 — dcat_dataset.license 값(소문자 비교)으로 찾는다.
ALLOWED_LICENSES: Dict[str, License] = {
    # https://open.canada.ca/en/open-government-licence-canada — 출처 표시 조건으로 복제·배포·상업적 이용 허용
    "open government licence - canada": License(
        "Open Government Licence - Canada", "other",
        "https://open.canada.ca/en/open-government-licence-canada",
        "출처 표시 필요: 'Contains information licensed under the Open Government Licence – Canada.'"),
    "cc-by-4.0": License("CC BY 4.0", "cc-by-4.0", "https://creativecommons.org/licenses/by/4.0/",
                         "저작자 표시 필요"),
    "cc0-1.0": License("CC0 1.0", "cc0-1.0", "https://creativecommons.org/publicdomain/zero/1.0/",
                       "조건 없음"),
}


@dataclass
class Eligibility:
    allowed: bool
    reasons: List[str] = field(default_factory=list)   # 불가 사유(사람이 읽는 문장)
    license: Optional[License] = None

    def public(self) -> Dict:
        lic = self.license
        return {"allowed": self.allowed, "reasons": self.reasons,
                "license": None if lic is None else
                {"name": lic.name, "hf_id": lic.hf_id, "link": lic.link, "attribution": lic.attribution}}


def eligibility(source_type: Optional[str], visibility: Optional[str], license_value: Optional[str]) -> Eligibility:
    reasons: List[str] = []
    if visibility != "PUBLIC":
        reasons.append("공개 범위가 '전체 공개'인 데이터만 외부로 내보낼 수 있습니다")
    if source_type in NO_EXPORT:
        reasons.append(NO_EXPORT[source_type])
    lic = ALLOWED_LICENSES.get((license_value or "").strip().lower())
    if lic is None and source_type not in NO_EXPORT:
        reasons.append("원천 라이선스가 재배포를 허용하는지 확인되지 않았습니다"
                       + (f" ({license_value})" if license_value else " (라이선스 정보 없음)"))
    return Eligibility(allowed=not reasons, reasons=reasons, license=lic)
