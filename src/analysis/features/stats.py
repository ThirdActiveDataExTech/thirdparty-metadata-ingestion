"""기술통계 특징 — 데이터셋이 "무엇을 얼마나" 담고 있는지 (B1).

컬럼 단위 통계(pandas `describe()`, 카디널리티, 결측률)는 **최소선에서 뺐다.**
대상인 `meta_datagokr_file`이 아직 0건이기 때문이다(정형 수집은 §7/A3).
적재되면 `scope='column'`으로 같은 테이블에 들어간다 — 그래서 `meta_feature`에
`scope`/`target` 컬럼을 미리 두었다.

여기서 내는 값은 전부 **그 자체로 과제 산출물**이다. "데이터셋에 무엇이 얼마나
있고 어떤 상태인가"를 기계가 읽을 수 있는 형태로 남기는 것이 1차년도 과업
"데이터 특징 추출 및 분석"의 최소선이다.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


def _percentile(sorted_vals: Sequence[float], q: float) -> Optional[float]:
    """가장 가까운 순위 방식. 값이 없으면 None."""
    if not sorted_vals:
        return None
    idx = min(len(sorted_vals) - 1, max(0, int(round(q * (len(sorted_vals) - 1)))))
    return sorted_vals[idx]


def length_distribution(lengths: Sequence[int]) -> Dict[str, Any]:
    """텍스트 길이 분포.

    평균만 남기지 않는 이유 — 본문 수집에 실패한 항목(제목만 있는 20자짜리)과
    정상 기사(2,000자)가 섞이면 평균은 둘 다 아닌 값이 된다. 분위수를 같이 둬야
    "절반은 짧다"가 보인다.
    """
    vals = sorted(int(v) for v in lengths if v is not None)
    if not vals:
        return {"count": 0}
    return {
        "count": len(vals),
        "mean": round(sum(vals) / len(vals), 1),
        "min": vals[0],
        "p50": _percentile(vals, 0.50),
        "p90": _percentile(vals, 0.90),
        "max": vals[-1],
    }


def build(dataset_id: str, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """원천별로 긁어온 수치를 meta_feature 행 목록으로 만든다.

    raw는 extract.py가 SQL로 모아 넘긴다. 여기서는 계산과 모양 결정만 한다 —
    DB를 안 보므로 테스트가 쉽다.
    """
    rows: List[Dict[str, Any]] = []

    def add(name: str, value: Any):
        if value is not None:
            rows.append({"feature_name": name, "value": value})

    add("item_count", raw.get("item_count"))
    add("chunk_count", raw.get("chunk_count"))
    add("vocab_size", raw.get("vocab_size"))

    if raw.get("lengths") is not None:
        add("text_length", length_distribution(raw["lengths"]))

    # 본문 보유율 — 뉴스·블로그만 해당. 스크래핑 실패율을 그대로 드러낸다.
    total, with_content = raw.get("item_count"), raw.get("with_content")
    if total and with_content is not None:
        add("content_rate", {"with_content": with_content, "total": total,
                             "ratio": round(with_content / total, 4)})

    lo, hi, days = raw.get("period_start"), raw.get("period_end"), raw.get("observed_days")
    if lo or hi:
        add("collected_period", {
            "start": lo.isoformat() if lo else None,
            "end": hi.isoformat() if hi else None,
            "observed_days": days,
        })
    return rows
