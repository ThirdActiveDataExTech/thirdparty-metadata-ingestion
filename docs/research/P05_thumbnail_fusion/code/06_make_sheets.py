"""P05 06a단계 — 라벨링 시트 생성 (PREREGISTRATION.md §0.3). **retrieval(05) 후 실행.**

05의 pool.json(쿼리별 후보 = Text∪Visual∪Fusion Top10 합집합)을 2인 독립·blind 라벨링
시트로 변환한다.

blind·독립·편향차단 규칙(사전 고정):
  - 시트에 **어느 시스템(Text/Visual/Fusion)이 뽑았는지 표시하지 않음**(blind pooling).
  - 후보를 **쿼리별로 셔플**(고정 seed)해 위치·시스템 편향 차단.
  - 두 라벨러가 **상호 라벨을 볼 수 없는 독립 파일**(labeler_A.csv / labeler_B.csv).
  - 라벨러는 제목·썸네일 + 실제 영상(짧은 skim) 확인 후 grade(0/1/2) 입력.

입력(data/):
  - retrieval/pool.json : 05 산출 (쿼리별 후보 video_id)
  - corpus.jsonl        : title·thumbnail_url 조인용(최종 eval 코퍼스)
출력(data/labeling/):
  - labeler_A.csv, labeler_B.csv : 동일 내용·동일 blind 순서, grade 칸 비움
  - LABELING_GUIDE.md            : 0/1/2 정의 + 1↔2 경계 예시(사전 배포)

실행(05 이후):
  PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/06_make_sheets.py
"""

import csv
import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
POOL_PATH = DATA_DIR / "retrieval" / "pool.json"
CORPUS_PATH = DATA_DIR / "corpus.jsonl"
OUT_DIR = DATA_DIR / "labeling"
SHUFFLE_SEED = 20260807   # 고정 → 재현 가능한 blind 순서

GUIDE = """# P05 관련성 라벨링 가이드 (2인 독립·blind)

각 행은 (검색 쿼리, 후보 영상) 쌍입니다. **이 영상이 이 쿼리에 답하는가**를 판단해
`grade` 칸에 0/1/2 중 하나를 적으세요. 제목·썸네일뿐 아니라 **영상을 짧게 열어 내용을
확인**하세요(시각 정보가 중요한 연구입니다).

## 등급 정의
- **2 (관련)**: 영상 주제가 쿼리의 핵심 정보 요구를 **직접** 다룸.
  - 예) 쿼리 "전기차 보조금" ↔ 전기차 국가보조금 정책을 설명하는 영상 → 2
- **1 (부분 관련)**: 쿼리 주제를 다루긴 하나 **부수적/일부만**, 또는 인접 주제.
  - 예) 쿼리 "전기차 보조금" ↔ 전기차 구매 후기 중 보조금이 잠깐 언급 → 1
- **0 (무관)**: 쿼리와 주제적 연결이 사실상 없음.
  - 예) 쿼리 "전기차 보조금" ↔ 일반 자동차 세차 영상 → 0

## 1 vs 2 경계(가장 중요 — 여기서 의견이 갈립니다)
- 영상의 **주제 자체**가 쿼리를 다루면 **2**, 쿼리 주제가 **곁가지로만** 나오면 **1**.
- 클릭베이트 제목이지만 실제 내용이 쿼리와 맞으면 **내용 기준**으로 판단(제목만 보지 말 것).
- 제목엔 있는데 내용은 거의 안 다루면 **1 또는 0**(내용 기준).

## 주의
- 다른 라벨러의 판단을 보거나 상의하지 마세요(독립 라벨링). 심각 불일치(0↔2)는 나중에
  별도 합의 단계에서 함께 재검토합니다.
- 이 영상이 어떤 검색 방식으로 뽑혔는지는 제공되지 않습니다(blind).
"""


def main():
    pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    meta = {}
    with CORPUS_PATH.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            meta[r["video_id"]] = (r.get("title", ""), r.get("thumbnail_url", ""))

    rng = random.Random(SHUFFLE_SEED)
    rows = []
    for qid, q in pool.items():
        cands = list(q["candidates"])
        rng.shuffle(cands)  # blind 순서
        for vid in cands:
            title, thumb = meta.get(vid, ("(코퍼스에 없음)", ""))
            rows.append({
                "query_id": qid, "query": q["query"], "category": q["category"],
                "video_id": vid, "title": title, "thumbnail_url": thumb,
                "url": f"https://www.youtube.com/watch?v={vid}", "grade": "",
            })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cols = ["query_id", "query", "category", "video_id", "title", "thumbnail_url", "url", "grade"]
    for who in ("A", "B"):
        with (OUT_DIR / f"labeler_{who}.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
    (OUT_DIR / "LABELING_GUIDE.md").write_text(GUIDE, encoding="utf-8")
    print(f"쿼리 {len(pool)}개 / 총 {len(rows)}쌍 → labeler_A.csv, labeler_B.csv (+ LABELING_GUIDE.md)")
    print(f"두 파일은 동일 blind 순서(seed={SHUFFLE_SEED}). 두 사람이 독립적으로 grade 입력.")


if __name__ == "__main__":
    main()
