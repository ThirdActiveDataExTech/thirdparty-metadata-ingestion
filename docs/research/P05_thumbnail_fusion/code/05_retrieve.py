"""P05 05단계 — Retrieval (PREREGISTRATION.md §0.5). **골격: query freeze 전 실행 금지.**

각 평가 쿼리에 대해 세 검색 시스템의 점수를 계산한다:
  - Text-only  : score = cos(mpnet(query), ret_txt_i)            (paraphrase-multilingual-mpnet)
  - Visual-only: score = cos(clip_mtxt(query), img_i)            (clip-ViT-B-32-multilingual-v1 ↔ CLIP 이미지)
  - Late Fusion: score = α·norm(text) + (1-α)·norm(visual)       (α 사전 grid 전수)

⚠️ 사전 고정(결과 보기 전, HARKing 방지):
  - **ALPHA_GRID 전수 평가**. 특정 α를 결과 보고 고르지 않는다(test leakage 금지).
  - **점수 정규화 = 쿼리별 min-max**(text/visual 스케일이 달라 융합 전 정규화 필요).
  - **Δrank = rank_text − rank_fusion**(양수 = fusion이 순위 개선). 07에서 사용.
  - **Pooling = Text Top10 ∪ Visual Top10 ∪ (α별 Fusion Top10 전체 합집합)** — α에 의존하지
    않도록 α-agnostic 합집합. POOL_TOPK=10 고정(§0.3).
  - gap 계산의 centering은 **gap 지표 전용**이며 retrieval 점수는 **raw cosine**을 쓴다(별개).

입력(data/):
  - embeddings/embeddings.npz : video_ids, img, ret_txt (02 산출; 최종 eval 코퍼스)
  - queries_frozen.json       : Query Pilot + 사람 검수로 freeze된 최종 평가 쿼리
                                [{query_id, query, category}] — **아직 없음(생성 후 실행)**
출력(data/retrieval/):
  - scores.npz : query_ids, video_ids, text_scores(Q×N), visual_scores(Q×N)  (07이 융합·Δrank 산출)
  - pool.json  : {query_id: {query, category, candidates:[video_id...]}}  (06 라벨링 시트 입력)

실행(‼️ query freeze 이후):
  PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/05_retrieve.py
"""

import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EMB_PATH = DATA_DIR / "embeddings" / "embeddings.npz"
QUERIES_PATH = DATA_DIR / "queries_frozen.json"
OUT_DIR = DATA_DIR / "retrieval"

RET_TXT_MODEL = "paraphrase-multilingual-mpnet-base-v2"       # Text 채널 = 코퍼스 ret_txt와 동일 인코더
CLIP_TXT_MODEL = "sentence-transformers/clip-ViT-B-32-multilingual-v1"  # Visual 채널 = CLIP 이미지 공간 정렬 텍스트 인코더

# ── 사전 고정 파라미터 (결과 보기 전) ─────────────────────────────
ALPHA_GRID = [round(0.1 * i, 1) for i in range(11)]  # 0.0 … 1.0 전수
POOL_TOPK = 10
DELTA_RANK_DEF = "rank_text - rank_fusion (positive = fusion improves rank)"


def _norm_rows(A):
    n = np.linalg.norm(A, axis=1, keepdims=True); n[n < 1e-9] = 1
    return A / n


def _minmax(v):
    lo, hi = float(v.min()), float(v.max())
    return (v - lo) / (hi - lo) if hi > lo else np.zeros_like(v)


def _topk_ids(scores, video_ids, k):
    idx = np.argsort(-scores)[:k]
    return [video_ids[i] for i in idx]


def main():
    d = np.load(EMB_PATH, allow_pickle=True)
    video_ids = [str(v) for v in d["video_ids"]]
    img = _norm_rows(d["img"].astype(np.float64))
    ret = _norm_rows(d["ret_txt"].astype(np.float64))

    raw = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))      # {_meta, queries:[...]} 또는 [...]
    queries = raw["queries"] if isinstance(raw, dict) else raw       # [{query_id, query, category}]
    q_texts = [q["query"] for q in queries]

    # 쿼리 인코딩 — 각 채널의 코퍼스 인코더와 '같은 공간'으로
    ret_model = SentenceTransformer(RET_TXT_MODEL)
    clip_model = SentenceTransformer(CLIP_TXT_MODEL)
    q_ret = _norm_rows(ret_model.encode(q_texts, convert_to_numpy=True, normalize_embeddings=True).astype(np.float64))
    q_clip = _norm_rows(clip_model.encode(q_texts, convert_to_numpy=True, normalize_embeddings=True).astype(np.float64))

    text_scores = q_ret @ ret.T        # Q×N (raw cos)
    visual_scores = q_clip @ img.T     # Q×N (raw cross-modal cos)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT_DIR / "scores.npz",
                        query_ids=np.array([q["query_id"] for q in queries]),
                        video_ids=np.array(video_ids),
                        text_scores=text_scores.astype(np.float32),
                        visual_scores=visual_scores.astype(np.float32),
                        alpha_grid=np.array(ALPHA_GRID))

    # Pooling: Text10 ∪ Visual10 ∪ (α별 Fusion10 전수 합집합) — α-agnostic
    pool = {}
    for i, q in enumerate(queries):
        cand = set(_topk_ids(text_scores[i], video_ids, POOL_TOPK))
        cand |= set(_topk_ids(visual_scores[i], video_ids, POOL_TOPK))
        tn, vn = _minmax(text_scores[i]), _minmax(visual_scores[i])
        for a in ALPHA_GRID:
            fused = a * tn + (1 - a) * vn
            cand |= set(_topk_ids(fused, video_ids, POOL_TOPK))
        pool[q["query_id"]] = {"query": q["query"], "category": q["category"],
                               "candidates": sorted(cand)}
    (OUT_DIR / "pool.json").write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")

    sizes = [len(v["candidates"]) for v in pool.values()]
    print(f"쿼리 {len(queries)}개 | pool 크기 평균 {np.mean(sizes):.1f} (min {min(sizes)}, max {max(sizes)})")
    print(f"저장: {OUT_DIR/'scores.npz'} , {OUT_DIR/'pool.json'}")
    print(f"Δrank 정의(고정): {DELTA_RANK_DEF}")


if __name__ == "__main__":
    main()
