"""P05 06a단계 — 라벨링 시트 생성 (PREREGISTRATION.md §0.3). **retrieval(05) 후 실행.**

05의 pool.json(쿼리별 후보 = Text∪Visual∪Fusion Top10 합집합)을 **3인 독립·blind** 라벨링
시트로 변환한다(median-of-3 집계, 2026-08-13 재-freeze).

blind·독립·편향차단 규칙(사전 고정):
  - 시트에 **어느 시스템(Text/Visual/Fusion)이 뽑았는지 표시하지 않음**(blind pooling).
  - 후보를 **쿼리별로 셔플**(고정 seed)해 위치·시스템 편향 차단.
  - 세 라벨러가 **상호 라벨을 볼 수 없는 독립 파일**(labeler_A/B/C.csv).
  - 라벨러는 제목·썸네일 + 실제 영상(짧은 skim) 확인 후 grade(0/1/2) 입력.
  - 집계 = **median-of-3**. A=B 쌍은 C가 값에 영향 없음(중앙값) → C가 시간 부족하면
    **불일치(A≠B) 쌍만** 마저 판정(06b_checkpoint.py). 최종 라벨은 어느 경우든 동일.

입력(data/):
  - retrieval/pool.json : 05 산출 (쿼리별 후보 video_id)
  - corpus.jsonl        : title·thumbnail_url 조인용(최종 eval 코퍼스)
출력(data/labeling/):
  - labeler_A/B/C.csv : 동일 내용·동일 blind 순서, grade 칸 비움
  - LABELING_GUIDE.md : 0/1/2 정의 + 1↔2 경계 예시(사전 배포)

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

GUIDE = """# P05 관련성 라벨링 가이드 (3인 독립·blind)

## 왜 이 라벨링을 하나요? (배경 — 처음 보셔도 됩니다)

**연구 한 줄 요약**: YouTube 영상 검색에서 **썸네일(대표 이미지)이 검색에 도움이 되는
경우가 언제인지**를 분석하는 연구입니다.

- **왜 사람이 정답을 매겨야 하나요?** 컴퓨터가 검색어마다 영상을 순위로 뽑아줍니다.
  그 순위가 **실제로 잘 맞는지 채점하려면** "이 검색어엔 이 영상이 정답"이라는 **사람
  기준의 정답지**가 필요합니다. 이게 없으면 검색 성능을 아예 잴 수 없습니다. **여러분이
  매기는 0/1/2가 바로 그 정답지(qrels)** 입니다.
- **왜 뒤섞여 있고, 어떤 방식이 뽑았는지 안 알려주나요?** 서로 다른 검색 방식(텍스트만/
  이미지만/둘 결합)의 결과를 **섞어서 blind로** 드립니다. 어느 방식이 뽑았는지 알면
  무의식적 편향이 생기므로, 오직 **"이 영상이 이 검색어에 맞나"**만 보고 판단하세요.
- **왜 3명이 따로 하나요?** 한 사람의 주관이 섞이지 않도록 3명이 **독립적으로** 매기고,
  최종 정답은 **세 판단의 중앙값(median)**으로 정합니다. 세 사람이 얼마나 일치했는지도
  신뢰도 지표로 함께 보고합니다. 그래서 **서로 상의하지 않는 것**이 중요합니다.
- **내 라벨이 뭘 결정하나요?** 이 정답지로 두 가지를 검증합니다 — ① 썸네일을 결합하면
  검색이 실제로 좋아지는가, ② 어떤 영상에서 특히 도움이 되는가. **연구 결론이 이 라벨
  품질에 달려 있습니다.**

## 무엇을 하나요

각 행은 (검색 쿼리, 후보 영상) 쌍입니다. **이 영상이 이 쿼리에 답하는가**를 판단해
`grade` 칸에 0/1/2 중 하나를 적으세요. 제목·썸네일뿐 아니라 **영상을 짧게 열어 내용을
확인**하세요(시각 정보가 중요한 연구입니다). 같은 영상이 여러 검색어 아래 반복될 수
있는데, **그때그때 "그 검색어" 기준으로** 다시 판단하시면 됩니다.

## 등급 정의
- **2 (관련)**: 영상 주제가 쿼리의 핵심 정보 요구를 **직접** 다룸.
  - 예) 쿼리 "전기차 보조금" ↔ 전기차 국가보조금 정책을 설명하는 영상 → 2
- **1 (부분 관련)**: 쿼리 주제를 다루긴 하나 **부수적/일부만**, 또는 인접 주제.
  - 예) 쿼리 "전기차 보조금" ↔ 전기차 구매 후기 중 보조금이 잠깐 언급 → 1
- **0 (무관)**: 쿼리와 주제적 연결이 사실상 없음.
  - 예) 쿼리 "전기차 보조금" ↔ 일반 자동차 세차 영상 → 0

## 쿼리 기준: '카테고리'가 아니라 '그 검색어의 특정 주제' (꼭 읽어주세요)
검색어는 "게임 로블록스"처럼 **[카테고리어 + 세부 주제]** 형태입니다. 판단은 **세부 주제
(로블록스)** 기준입니다. **같은 카테고리(게임)라도 다른 주제면 무관(0)** 입니다.
- 예) "게임 로블록스" ↔ **롤(LoL) 영상 → 0** (둘 다 게임이지만 로블록스가 아님)
- 예) "게임 로블록스" ↔ 여러 게임을 비교하며 로블록스가 한 부분으로 등장 → **1**
- 예) "게임 로블록스" ↔ 로블록스 플레이·리뷰·공략 → **2**
- 예) "자동차 냉각수" ↔ 일반 세차 영상 → **0** (냉각수 주제가 아님)

즉 **"같은 분야니까 관련"이 아니라 "그 검색어가 원하는 바로 그 주제인가"** 로 판단하세요.

## 같은 영상이 여러 검색어에 나올 때 (등급이 달라도 정상입니다)
하나의 영상이 서로 다른 검색어 아래 여러 번 나올 수 있습니다. **그때마다 "지금 이 검색어"
기준으로 독립적으로** 판단하세요. **같은 영상이라도 검색어에 따라 등급이 달라지는 것이 정상이고
맞습니다.** 앞선 검색어에서 몇 점을 줬는지 기억하려 애쓰거나 일부러 같게 맞출 필요가 없습니다.

- 예) 어떤 영상이 **"여러 모바일게임을 소개·평가하는 영상"** 이라고 합시다.
  - 검색어 **"게임 추천 모바일"** 아래 → 모바일게임을 추천하는 내용이므로 **2(직접 관련)**.
  - 검색어 **"게임 리뷰"** 아래 → 게임을 실제로 **리뷰(장단점·평가)** 하면 **2**, 단순 목록·추천
    나열에 그쳐 리뷰 성격이 약하면 **1**.
  - → 같은 영상이 한 검색어엔 **2**, 다른 검색어엔 **1**일 수 있습니다.

핵심 질문은 **"이 영상이 (일반적으로) 좋은 영상인가?"가 아니라 "이 영상이 지금 이 검색어가
찾는 것을 주는가?"** 입니다. 매번 그 검색어에 맞춰 새로 판단하세요.

## 1 vs 2 경계(가장 중요 — 여기서 의견이 갈립니다)
- 영상의 **주제 자체**가 쿼리를 다루면 **2**, 쿼리 주제가 **곁가지로만** 나오면 **1**.
- 클릭베이트 제목이지만 실제 내용이 쿼리와 맞으면 **내용 기준**으로 판단(제목만 보지 말 것).
- 제목엔 있는데 내용은 거의 안 다루면 **1 또는 0**(내용 기준).

## 주의
- 다른 라벨러의 판단을 보거나 상의하지 마세요(독립 라벨링). 세 사람의 판단은 나중에
  **중앙값(median)** 으로 자동 합쳐지므로 별도 합의 회의는 없습니다.
- 이 영상이 어떤 검색 방식으로 뽑혔는지는 제공되지 않습니다(blind).

## 파일 저장 (중요! — Numbers 주의)
- `grade` 열에만 0/1/2를 입력하고 **CSV 형식 그대로 저장**하세요. **다른 열·행 순서·행 수는
  건드리지 마세요.**
- ⚠️ macOS에서 CSV를 더블클릭하면 **Numbers**로 열립니다. 그냥 저장(⌘S)하면
  **`labeler_X.numbers`라는 별도 파일**로 저장되고 **원본 `labeler_X.csv`는 그대로 비어 있습니다**
  → 분석 파이프라인이 라벨을 **하나도 못 읽습니다.**
- **해결책(둘 중 하나):**
  1. Numbers로 작업했다면 → **파일 → 다음으로 내보내기 → CSV…** 로 **원래 `labeler_X.csv`를
     덮어쓰기**(인코딩 UTF-8). 매 작업 후 반복.
  2. 더 안전하게: 처음부터 **LibreOffice Calc**(⌘S 시 "CSV 형식 유지" 선택) 또는
     **Google Sheets**(가져오기 → 편집 → CSV로 다운로드)로 작업 → CSV가 그대로 유지됨.
- 저장 후, CSV를 텍스트 편집기로 열어 `grade` 값이 실제로 채워졌는지 한 번 확인하세요.

## ⚠️ 절대 주의 — video_id가 `#NAME?`로 깨지는 문제 (Excel/Numbers 수식 오해)
`video_id`에는 **`-`(하이픈)으로 시작하는 값**이 있습니다(예: `-Cj3JqvSrrE`). Excel/Numbers는
`-`나 `=`, `+`로 시작하는 셀을 **수식으로 착각**해서, 그냥 열고 저장만 해도 그 셀을
**`#NAME?`(오류값)로 파괴**합니다. 이러면 해당 영상의 라벨이 무효가 됩니다.
- **가장 안전**: CSV를 **스프레드시트로 열지 말고** 텍스트/CSV 전용 에디터에서 `grade` 열만 편집.
- 스프레드시트를 꼭 써야 하면:
  - **Google Sheets**: 새 시트 → 가져오기 시 데이터를 **"텍스트로"** 지정(자동 변환 끄기).
  - **LibreOffice Calc**: 열 때 뜨는 가져오기 대화상자에서 **"특수 숫자 감지" 체크 해제**.
- 저장 후 `video_id` 열에 **`#NAME?`가 없는지** 반드시 눈으로 확인하세요.
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
    for who in ("A", "B", "C"):
        with (OUT_DIR / f"labeler_{who}.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
    (OUT_DIR / "LABELING_GUIDE.md").write_text(GUIDE, encoding="utf-8")
    print(f"쿼리 {len(pool)}개 / 총 {len(rows)}쌍 → labeler_A/B/C.csv (+ LABELING_GUIDE.md)")
    print(f"세 파일은 동일 blind 순서(seed={SHUFFLE_SEED}). 세 사람이 독립적으로 grade 입력.")
    print("C가 시간 부족 시: A·B 완료 후 06b_checkpoint.py로 불일치 쌍만 추려 마무리 가능.")


if __name__ == "__main__":
    main()
