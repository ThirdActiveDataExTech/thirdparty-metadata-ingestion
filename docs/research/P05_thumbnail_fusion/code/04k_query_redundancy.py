"""P05 04k단계 — Query–Query Redundancy Audit (DIAGNOSTIC ONLY. 삭제·재표집 안 함).

문제: '동물 감동' ≈ '동물 감동영상'처럼 같은 category 안 4개 중 일부가 사실상 같은 검색
의도(near-duplicate query family)일 수 있다 → 평가셋의 '유효 다양성'이 4 미만으로 떨어짐.
(주의: '자동차 가죽청소' vs '가죽코팅'처럼 category만 공유·intent는 다른 것과 구분해야 함.)

측정(3 신호, 삭제 아님):
  1) **결과 overlap(핵심)**: 두 쿼리의 **Fusion(α=0.5) Top-10 / Text Top-10** 영상집합 Jaccard.
     검색 결과가 거의 같으면 평가 관점에서 중복. (Text는 visual hub 오염 덜 타 교차검증용.)
  2) **embedding**: category mean-centering(이방성 제거)한 mpnet 쿼리 cos.
  3) **lexical**: 공백 토큰 Jaccard(카테고리 공유어 제외).

⚠️ threshold는 **표시용**. 여기서 쿼리를 KEEP/EXCLUDE·재표집하지 않는다. 심각도만 측정.
   판단: category당 의심쌍 수 → 대부분 0~1이면 정상 / 다수 category가 2~3이면 sampling 재검토.

입력: queries_frozen.json, retrieval/scores.npz, retrieval/pool.json
출력: 콘솔 + data/query_redundancy_audit.json (변경 없음)

실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/04k_query_redundancy.py
"""

import json
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
QUERIES_PATH = DATA_DIR / "queries_frozen.json"
SCORES_PATH = DATA_DIR / "retrieval" / "scores.npz"
MODEL = "paraphrase-multilingual-mpnet-base-v2"
TOPK = 10
SUSPECT_RESULT_JACCARD = 0.40   # 표시용: Fusion Top-10 겹침 ≥ 이 값이면 '중복 의심'


def _minmax(v):
    lo, hi = float(v.min()), float(v.max())
    return (v - lo) / (hi - lo) if hi > lo else np.zeros_like(v)


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if (a or b) else 0.0


def main():
    raw = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
    queries = raw["queries"] if isinstance(raw, dict) else raw
    qmeta = {q["query_id"]: q for q in queries}

    z = np.load(SCORES_PATH, allow_pickle=True)
    qids = [str(x) for x in z["query_ids"]]
    vids = [str(x) for x in z["video_ids"]]
    text, vis = z["text_scores"].astype(np.float64), z["visual_scores"].astype(np.float64)

    # 쿼리별 Text Top-10 / Fusion(α=0.5) Top-10 영상집합
    text_top, fus_top = {}, {}
    for i, qid in enumerate(qids):
        text_top[qid] = [vids[j] for j in np.argsort(-text[i])[:TOPK]]
        fused = 0.5 * _minmax(text[i]) + 0.5 * _minmax(vis[i])
        fus_top[qid] = [vids[j] for j in np.argsort(-fused)[:TOPK]]

    # centered mpnet(카테고리별) — embedding 유사도
    q_texts = [qmeta[qid]["query"] for qid in qids]
    emb = SentenceTransformer(MODEL).encode(q_texts, convert_to_numpy=True,
                                            normalize_embeddings=True).astype(np.float64)
    emb_of = {qid: emb[i] for i, qid in enumerate(qids)}

    bycat = defaultdict(list)
    for qid in qids:
        bycat[qmeta[qid]["category"]].append(qid)

    report = {"_meta": {"topk": TOPK, "suspect_result_jaccard": SUSPECT_RESULT_JACCARD,
                        "note": "DIAGNOSTIC only. 결과 overlap=핵심 신호. 삭제/재표집 안 함."},
              "categories": {}, "summary": {}}
    cat_suspects = {}

    print("=== Query–Query 중복 진단 (category 내 6쌍; 결과 overlap 핵심) ===")
    print("  Fus=Fusion Top10 Jaccard, Txt=Text Top10 Jaccard, Emb=centered cos, Lex=token Jaccard\n")
    for cat, ids in bycat.items():
        # 카테고리 centering
        M = np.array([emb_of[q] for q in ids])
        Mc = M - M.mean(0, keepdims=True)
        nrm = np.linalg.norm(Mc, axis=1, keepdims=True); nrm[nrm < 1e-9] = 1
        Mc = Mc / nrm
        cpos = {q: k for k, q in enumerate(ids)}
        catword = None  # 공유 category 토큰 추정(가장 흔한 토큰)
        toks_all = [set(qmeta[q]["query"].split()) for q in ids]
        common = set.intersection(*toks_all) if toks_all else set()

        pairs = []
        suspects = 0
        print(f"── [{cat}] {', '.join(qmeta[q]['query'] for q in ids)}")
        for a, b in combinations(ids, 2):
            fus = jaccard(fus_top[a], fus_top[b])
            txt = jaccard(text_top[a], text_top[b])
            embc = float(Mc[cpos[a]] @ Mc[cpos[b]])
            ta = set(qmeta[a]["query"].split()) - common
            tb = set(qmeta[b]["query"].split()) - common
            lex = jaccard(ta, tb)
            suspect = fus >= SUSPECT_RESULT_JACCARD
            suspects += suspect
            pairs.append({"a": qmeta[a]["query"], "b": qmeta[b]["query"],
                          "fusion_jaccard": round(fus, 2), "text_jaccard": round(txt, 2),
                          "centered_cos": round(embc, 2), "lex_jaccard": round(lex, 2),
                          "suspect": suspect})
            mark = "  ⚠️중복의심" if suspect else ""
            print(f"     Fus={fus:.2f} Txt={txt:.2f} Emb={embc:+.2f} Lex={lex:.2f}  "
                  f"'{qmeta[a]['query']}' ↔ '{qmeta[b]['query']}'{mark}")
        report["categories"][cat] = {"queries": [qmeta[q]["query"] for q in ids],
                                     "pairs": pairs, "suspect_pairs": suspects}
        cat_suspects[cat] = suspects
        print()

    n_cat_with_suspect = sum(1 for v in cat_suspects.values() if v >= 1)
    n_cat_multi = sum(1 for v in cat_suspects.values() if v >= 2)
    report["summary"] = {"suspect_pairs_per_category": cat_suspects,
                         "n_categories_with_>=1_suspect": n_cat_with_suspect,
                         "n_categories_with_>=2_suspect": n_cat_multi,
                         "total_suspect_pairs": sum(cat_suspects.values())}
    print("=== 요약 ===")
    print(f"  category별 중복의심 쌍(Fusion Jaccard≥{SUSPECT_RESULT_JACCARD}): " +
          ", ".join(f"{c}={n}" for c, n in sorted(cat_suspects.items(), key=lambda x: -x[1])))
    print(f"  의심쌍 있는 category: {n_cat_with_suspect}/14  |  2쌍 이상: {n_cat_multi}/14  |  총 의심쌍: {sum(cat_suspects.values())}")
    print("  → 대부분 0~1이면 정상(개별 처리). 다수 category가 2+이면 cluster-aware 재표집 검토.")

    (DATA_DIR / "query_redundancy_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {DATA_DIR/'query_redundancy_audit.json'} (진단 전용)")


if __name__ == "__main__":
    main()
