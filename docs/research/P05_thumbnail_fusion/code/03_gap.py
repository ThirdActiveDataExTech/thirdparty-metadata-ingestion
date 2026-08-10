"""P05 03단계 — gap 계산 (PREREGISTRATION.md §0.4).

gap = 이미지(썸네일)와 텍스트(제목)의 CLIP 유사도로부터 "시각-텍스트 의미 격차"를 잰다.
02에서 만든 임베딩(embeddings.npz)만 읽어 계산한다(쿼터·라벨링 무관).

두 정의를 **모두** 산출한다(§0.4 ablation 계획):
  - raw_gap_i      = 1 - cos(img_i, gtxt_i)
  - centered_gap_i = 1 - cos(center(img_i), center(gtxt_i))   ← **primary**
    center = 모달별 코퍼스 평균 차감 후 재정규화(이방성/modality-gap offset 제거).

centered가 사전등록 primary(construct validity 근거, §0.4), raw는 투명성 ablation용.
05단계에서 H2(Spearman(gap, Δrank))를 raw·centered 양쪽으로 돌려 비교한다.

출력(data/):
  - gap.csv  : video_id, category, raw_gap, centered_gap  (커밋 대상 — 분석 재현용)
  - gap.npz  : 배열 형태(하류 단계용) + µ 벡터(재현용)

실행: 저장소 루트에서 (02_embed.py 실행 후)
  PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/03_gap.py
"""

import csv
import json
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EMB_PATH = DATA_DIR / "embeddings" / "embeddings.npz"
CORPUS_PATH = DATA_DIR / "corpus.jsonl"
GAP_CSV = DATA_DIR / "gap.csv"
GAP_NPZ = DATA_DIR / "embeddings" / "gap.npz"


def _normalize(A):
    n = np.linalg.norm(A, axis=1, keepdims=True)
    n[n < 1e-9] = 1
    return A / n


def main():
    d = np.load(EMB_PATH, allow_pickle=True)
    vids = [str(v) for v in d["video_ids"]]
    img = d["img"].astype(np.float64)
    gtxt = d["gap_txt"].astype(np.float64)

    # 카테고리 매핑(보고·분석용)
    cat = {}
    with CORPUS_PATH.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            cat[r["video_id"]] = r["sampled_category_name"]

    # raw gap
    I, G = _normalize(img), _normalize(gtxt)
    raw_gap = 1.0 - np.sum(I * G, axis=1)

    # centered gap (primary) — 모달별 평균 차감 후 재정규화
    mu_img, mu_gtxt = img.mean(0), gtxt.mean(0)
    Ic = _normalize(img - mu_img)
    Gc = _normalize(gtxt - mu_gtxt)
    cen_gap = 1.0 - np.sum(Ic * Gc, axis=1)

    # 저장
    with GAP_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["video_id", "category", "raw_gap", "centered_gap"])
        for v, rg, cg in zip(vids, raw_gap, cen_gap):
            w.writerow([v, cat.get(v, "?"), f"{rg:.6f}", f"{cg:.6f}"])
    np.savez_compressed(GAP_NPZ, video_ids=np.array(vids),
                        raw_gap=raw_gap.astype(np.float32),
                        centered_gap=cen_gap.astype(np.float32),
                        mu_img=mu_img.astype(np.float32), mu_gtxt=mu_gtxt.astype(np.float32))

    # 요약 보고
    def stat(name, g):
        print(f"  {name:<12} min {g.min():.3f} / mean {g.mean():.3f} / max {g.max():.3f} / std {g.std():.3f}")
    print(f"N={len(vids)}")
    stat("raw_gap", raw_gap)
    stat("centered_gap", cen_gap)
    try:
        from scipy.stats import spearmanr
        print(f"  raw↔centered Spearman ρ={spearmanr(raw_gap, cen_gap).correlation:.3f} (안정성 지표)")
    except Exception:
        pass
    print("\n[카테고리별 centered_gap 평균]")
    cats = np.array([cat.get(v, "?") for v in vids])
    for c in sorted(set(cats)):
        m = cats == c
        print(f"  {c:<10} n={m.sum():>3}  gap {cen_gap[m].mean():.3f} (std {cen_gap[m].std():.3f})")
    print(f"\n✅ 저장: {GAP_CSV} , {GAP_NPZ}")


if __name__ == "__main__":
    main()
