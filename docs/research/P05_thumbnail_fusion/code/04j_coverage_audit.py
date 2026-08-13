"""P05 04j단계 — Query–Corpus Coverage Audit (DIAGNOSTIC ONLY. 쿼리 KEEP/EXCLUDE 안 함).

frozen 56 쿼리에 대해, **코퍼스 840편에 의미적으로 가까운 제목이 존재하는지**를 약한 coverage
신호로 펼친다. 라벨링 전에 "진행 가능한가 / 특정 category가 체계적으로 안 맞는가"만 본다.

⚠️ 이 감사의 엄격한 정의(피드백 2026-08-13 반영):
  - **mpnet 제목 유사도 = relevance 판정이 아니라 "코퍼스에 이 쿼리와 의미적으로 가까운
    제목이 있는지"에 대한 약한 coverage 신호일 뿐.** 낮다고 관련 영상이 없다는 뜻이 아니다.
  - **text-편향**: 이 신호는 Text 채널(제목 mpnet)이라, **썸네일(visual)로만 관련된 영상은
    안 잡힌다.** 따라서 coverage 낮음으로 쿼리를 절대 제거하지 않는다.
  - **가장 중요한 출력은 Top-5 제목 자체**(사람이 빠르게 sanity check). 숫자는 표시용.
  - **04j는 쿼리를 KEEP/EXCLUDE 하지 않는다.** 오직 진단 라벨(COVERAGE_LIKELY / COVERAGE_WEAK)
    + category 요약(전부 약하면 CATEGORY_LEVEL_CONCERN)만 만든다.
  - 이 단계에선 "coverage 낮음"과 "retrieval 실패"를 **구분할 수 없다** → retrieval 실패는
    확정하지 않고 **RETRIEVAL_FAILURE_CANDIDATE**로만(실제 retrieval+relevance 후 확정).
  - **seed 영상 ↔ 쿼리 직접 연결 조건을 새로 만들지 않는다**(설계 훼손 금지).
  - 개별 "관련 0"은 라벨링 후 **사전등록 zero-relevance 규칙**이 처리한다(여기서 X).

유일한 action 트리거: **한 category의 4개가 모두 약함 → 사람 설계검토**(균일 규칙, cherry-pick 아님).

입력: data/embeddings/embeddings.npz(video_ids, ret_txt), corpus.jsonl(title), queries_frozen.json
출력: 콘솔 리포트 + data/coverage_audit.json (변경 없음)

실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/04j_coverage_audit.py
"""

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EMB_PATH = DATA_DIR / "embeddings" / "embeddings.npz"
CORPUS_PATH = DATA_DIR / "corpus.jsonl"
QUERIES_PATH = DATA_DIR / "queries_frozen.json"
OUT_PATH = DATA_DIR / "coverage_audit.json"
MODEL = "paraphrase-multilingual-mpnet-base-v2"

# 표시용 신호 밴드(판정 아님, centered 스케일). max 최근접 유사도 기준.
STRONG = 0.35   # 이상이면 COVERAGE_LIKELY(코퍼스에 가까운 제목 존재 신호)
WEAK = 0.20     # 미만이면 COVERAGE_WEAK(신호 약함 — 관련 없음이 아니라 text로 안 잡힘 가능)


def _norm(A):
    n = np.linalg.norm(A, axis=1, keepdims=True); n[n < 1e-9] = 1
    return A / n


def tier(mx):
    return "LIKELY" if mx >= STRONG else ("WEAK" if mx < WEAK else "UNCERTAIN")


def main():
    emb = np.load(EMB_PATH, allow_pickle=True)
    vids = [str(v) for v in emb["video_ids"]]
    ret = _norm(emb["ret_txt"].astype(np.float64))    # 코퍼스 제목 mpnet
    title = {}
    with CORPUS_PATH.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line); title[r["video_id"]] = r.get("title", "")

    raw = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
    queries = raw["queries"] if isinstance(raw, dict) else raw

    q_emb = _norm(SentenceTransformer(MODEL).encode(
        [q["query"] for q in queries], convert_to_numpy=True, normalize_embeddings=True).astype(np.float64))

    # ★ 이방성(anisotropy) 제거: 코퍼스 평균(hub 방향) 차감 후 재정규화 → 진짜 최근접이 드러남.
    #   (raw cos는 한국어 mpnet 이방성으로 뭐든 0.5~0.8 + hub 제목 반복 → 오해 소지)
    mu = ret.mean(axis=0, keepdims=True)
    retc = _norm(ret - mu)
    q_embc = _norm(q_emb - mu)

    per_q = []
    for i, q in enumerate(queries):
        sims = q_embc[i] @ retc.T          # centered 최근접(핵심)
        top = np.argsort(-sims)[:5]
        top5 = [{"video_id": vids[j], "title": title.get(vids[j], ""), "sim": round(float(sims[j]), 3)} for j in top]
        mx = float(sims[top[0]])
        per_q.append({"query_id": q["query_id"], "query": q["query"], "category": q["category"],
                      "max_sim": round(mx, 3), "mean_top5": round(float(sims[top].mean()), 3),
                      "n_ge_0.5": int((sims >= 0.5).sum()), "n_ge_0.4": int((sims >= 0.4).sum()),
                      "signal": tier(mx), "top5": top5})

    # category 요약: 전부 WEAK이면 CATEGORY_LEVEL_CONCERN
    bycat = defaultdict(list)
    for r in per_q:
        bycat[r["category"]].append(r)
    cat_summary = []
    for cat, rows in bycat.items():
        tiers = [r["signal"] for r in rows]
        concern = all(t == "WEAK" for t in tiers)
        cat_summary.append({"category": cat, "n": len(rows),
                            "LIKELY": tiers.count("LIKELY"), "UNCERTAIN": tiers.count("UNCERTAIN"),
                            "WEAK": tiers.count("WEAK"),
                            "flag": "CATEGORY_LEVEL_CONCERN" if concern else "OK",
                            "mean_max_sim": round(float(np.mean([r["max_sim"] for r in rows])), 3)})
    cat_summary.sort(key=lambda c: c["mean_max_sim"])

    # ── 콘솔: Top-5를 사람이 빠르게 볼 수 있게(핵심 출력) ──
    print("=== 쿼리별 coverage 신호 + 코퍼스 최근접 Top-5 제목(사람 sanity check) ===")
    print("⚠️ sim은 relevance 아님 = 'text로 가까운 제목 존재' 약한 신호. Top-5 제목을 직접 보세요.\n")
    for cat in [c["category"] for c in cat_summary]:
        print(f"── [{cat}] ──")
        for r in bycat[cat]:
            print(f"  {r['query_id']} '{r['query']}'  max={r['max_sim']} [{r['signal']}]  (≥0.5: {r['n_ge_0.5']}편)")
            for t in r["top5"][:3]:
                print(f"        {t['sim']:>5}  {t['title'][:46]}")
        print()

    print("=== category 요약 (mean_max_sim 낮은 순 = 관심 우선) ===")
    print(f"  {'category':<12} {'n':>2} {'LIKELY':>6} {'UNCERT':>6} {'WEAK':>5} {'meanMax':>8}  flag")
    for c in cat_summary:
        print(f"  {c['category']:<12} {c['n']:>2} {c['LIKELY']:>6} {c['UNCERTAIN']:>6} {c['WEAK']:>5} "
              f"{c['mean_max_sim']:>8}  {c['flag']}")
    concerns = [c["category"] for c in cat_summary if c["flag"] != "OK"]
    print(f"\nCATEGORY_LEVEL_CONCERN(4개 전부 WEAK): {concerns if concerns else '없음'}")
    print("→ concern 없으면: frozen 56 유지하고 라벨링 진행. concern 있으면: 그 category만 설계검토(균일 규칙).")

    OUT_PATH.write_text(json.dumps({"_meta": {"model": MODEL, "bands": {"STRONG": STRONG, "WEAK": WEAK},
                                              "note": "DIAGNOSTIC only. sim=weak text-coverage signal, not relevance. no keep/exclude."},
                                    "per_query": per_q, "category_summary": cat_summary},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {OUT_PATH} (진단 전용, 아무것도 변경 안 함)")


if __name__ == "__main__":
    main()
