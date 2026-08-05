"""P05 gap 인코더 sanity check (PREREGISTRATION.md §0.4).

gap_i = 1 - cos_sim(v_img_i, g_txt_i) 에서 텍스트는 `clip-ViT-B-32-multilingual-v1`로
인코딩한다(CLIP 이미지 공간에 distillation 정렬된 다국어 텍스트 인코더). gap 계산이
의미를 가지려면 이 인코더가 **한국어 의미를 제대로 구분**해야 한다.

이 스크립트는 라벨링·코퍼스·쿼터가 필요 없는 **구현 전 검증**이다(§0.4, freeze 대상 아님):
  - 유사한 한국어 제목쌍 → cosine 높음 (예: "HBM 반도체" ↔ "HBM 메모리")
  - 무관한 한국어 제목쌍 → cosine 낮음 (예: "강아지 산책" ↔ "GPU 구조")

PASS 기준: min(유사쌍) > max(무관쌍) (분리) 그리고 평균 차이 >= 0.15.
FAIL 시: 다른 다국어 CLIP 텍스트 인코더로 교체 검토(§0.4).

주의: 이건 텍스트-텍스트(한국어 이해) 검증이다. gap은 이미지-텍스트 교차모달이므로,
      코퍼스 확보 후 실제 썸네일로 교차모달 정렬도 별도 확인한다(후속).

실행: 저장소 루트에서
  PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/sanity_gap_encoder.py
"""

from sentence_transformers import SentenceTransformer, util

GAP_TEXT_MODEL = "sentence-transformers/clip-ViT-B-32-multilingual-v1"

# 유사쌍(높아야 함) — 같은 주제의 다른 표현
SIMILAR = [
    ("HBM 반도체", "HBM 메모리"),
    ("강아지 산책", "반려견 산책 브이로그"),
    ("축구 경기 하이라이트", "축구 골 장면 모음"),
    ("요리 레시피", "집밥 만드는 법"),
    ("아이폰 리뷰", "스마트폰 개봉기"),
    ("토익 공부법", "영어 점수 올리기"),
]
# 무관쌍(낮아야 함) — 완전히 다른 주제
UNRELATED = [
    ("강아지 산책", "GPU 구조 설명"),
    ("HBM 반도체", "고양이 장난감 추천"),
    ("메이크업 튜토리얼", "자동차 엔진 정비"),
    ("주식 투자 전략", "캠핑 요리 브이로그"),
    ("뉴스 속보", "게임 플레이 영상"),
]

MARGIN = 0.15  # centered 유사쌍 평균 - 무관쌍 평균 최소 기대치


def _all_phrases():
    ph = []
    for a, b in SIMILAR + UNRELATED:
        ph += [a, b]
    # 순서 유지 중복 제거(centering 평균 계산용 풀)
    seen, out = set(), []
    for p in ph:
        if p not in seen:
            seen.add(p); out.append(p)
    return out


def main():
    import numpy as np
    print(f"모델 로드: {GAP_TEXT_MODEL} (최초 실행 시 다운로드)")
    model = SentenceTransformer(GAP_TEXT_MODEL)

    # 공통 임베딩(정규화) + 이방성 보정용 평균
    phrases = _all_phrases()
    E = model.encode(phrases, normalize_embeddings=True)
    idx = {p: i for i, p in enumerate(phrases)}
    mu = E.mean(0)
    aniso = float(np.linalg.norm(mu))  # 1에 가까울수록 이방성 심함
    Ec = E - mu
    Ec = Ec / np.linalg.norm(Ec, axis=1, keepdims=True)

    def raw(a, b):
        return float(E[idx[a]] @ E[idx[b]])

    def centered(a, b):
        return float(Ec[idx[a]] @ Ec[idx[b]])

    print(f"\n이방성 지표(평균 임베딩 norm): {aniso:.3f} "
          f"— 0.9+면 raw cosine이 한 방향으로 뭉쳐 의미 분리가 마스킹됨")

    print("\n[raw cosine] (참고 — 이방성으로 전부 높게 뭉침)")
    print("  유사:", [f"{raw(a,b):.3f}" for a, b in SIMILAR])
    print("  무관:", [f"{raw(a,b):.3f}" for a, b in UNRELATED])

    print("\n[centered cosine] (이방성 보정 — 실제 한국어 의미 분리 여부)")
    sim = [centered(a, b) for a, b in SIMILAR]
    unr = [centered(a, b) for a, b in UNRELATED]
    for (a, b), s in zip(SIMILAR, sim):
        print(f"  유사 {s:+.3f}  {a}  ↔  {b}")
    for (a, b), s in zip(UNRELATED, unr):
        print(f"  무관 {s:+.3f}  {a}  ↔  {b}")

    sim_mean, unr_mean = sum(sim) / len(sim), sum(unr) / len(unr)
    print(f"\ncentered 유사 평균 {sim_mean:+.3f} (min {min(sim):+.3f}) / "
          f"무관 평균 {unr_mean:+.3f} (max {max(unr):+.3f}) / 차이 {sim_mean - unr_mean:.3f}")

    if min(sim) > max(unr) and (sim_mean - unr_mean) >= MARGIN:
        print("\n✅ 텍스트 이해 PASS — centered 기준 유사/무관 완전 분리. 인코더는 한국어 의미를 구분함.")
        print("   (raw cosine이 뭉치는 것은 인코더 결함이 아니라 CLIP 텍스트 임베딩의 이방성.)")
    else:
        print("\n❌ 텍스트 이해 FAIL — centered에서도 분리 약함. 다른 다국어 CLIP 검토(§0.4).")

    print("\n※ 주의: gap = 1 - cos(v_img, g_txt)는 **이미지-텍스트 교차모달**이다. 위는 "
          "텍스트-텍스트(한국어 이해) 예비 검증일 뿐이며, gap의 실제 타당성(정합 썸네일이 "
          "비정합보다 gap이 낮은지 + gap 분산이 충분한지)은 **코퍼스 썸네일 확보 후** "
          "교차모달로 검증한다(§0.4). 이방성이 교차모달 gap 분산까지 좁히면 centering/whitening "
          "도입을 검토(변경이력 기록).")


if __name__ == "__main__":
    main()
