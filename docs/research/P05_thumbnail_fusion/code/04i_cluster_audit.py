"""P05 04i단계 — 하위주제 편중 진단 (DIAGNOSTIC ONLY, 아무것도 바꾸지 않음).

목적: "자동차 표본이 세차/디테일링으로 쏠렸다"가 자동차 국소 문제인지, 14개 카테고리
전반 현상인지를 **숫자로** 본다. 여기서는 **어떤 쿼리도 삭제·재표집하지 않는다.**

측정(2 지표):
  1) **표본 clumping(threshold-free, 핵심)**: 현재 선정된 4개의 평균 쌍유사도(mpnet cos)에서
     그 카테고리 eligible 전체의 평균 쌍유사도를 뺀 값. **+ 클수록 현재 4개가 pool 평균보다
     서로 뭉쳐 있음**(= 하위주제 쏠림). threshold 무관 → 카테고리 간 직접 비교 가능.
  2) **하위주제 구조(참고)**: eligible을 cos 유사도 union-find로 묶어(고정 T) 하위주제 그룹과
     '최대 그룹 점유율'을 보여줌. 현재 4개가 몇 개 그룹에 걸치는지도 표시.

인코더: paraphrase-multilingual-mpnet-base-v2 (검색용과 동일).
입력: query_curation_adjudicated.json(eligible=KEEP), query_sample.json(현재 4개)
출력: 콘솔 리포트 + data/cluster_audit.json (변경 없음)

실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/04i_cluster_audit.py
"""

import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ADJ_PATH = DATA_DIR / "query_curation_adjudicated.json"
SAMPLE_PATH = DATA_DIR / "query_sample.json"
OUT_PATH = DATA_DIR / "cluster_audit.json"
MODEL = "paraphrase-multilingual-mpnet-base-v2"
UF_THRESHOLD = 0.40   # centered 공간의 하위주제 그룹 표시용(참고). 핵심 지표는 threshold-free.


def union_find(sim, thr):
    """sim[i][j] >= thr면 병합. 하위주제 그룹(참고용) 반환."""
    n = len(sim)
    parent = list(range(n))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for i in range(n):
        for j in range(i + 1, n):
            if sim[i][j] >= thr:
                parent[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def mean_pairwise(sim, idx):
    if len(idx) < 2:
        return float("nan")
    vals = [sim[a][b] for k, a in enumerate(idx) for b in idx[k + 1:]]
    return float(np.mean(vals))


def main():
    adj = json.loads(ADJ_PATH.read_text(encoding="utf-8"))
    smp = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))

    # 카테고리별 eligible 쿼리 + 현재 선정 4개
    per_cat = {}
    for cid, c in adj["categories"].items():
        keeps = [it["query"] for it in c["items"] if it["adjudicated_decision"] == "KEEP"]
        per_cat[c["name"]] = keeps
    selected = {name: smp["categories"][name]["selected"] for name in per_cat}

    # 전체 임베딩 1회
    all_q = sorted({q for qs in per_cat.values() for q in qs})
    print(f"임베딩 {len(all_q)}쿼리 (mpnet) …")
    model = SentenceTransformer(MODEL)
    emb = model.encode(all_q, convert_to_numpy=True, normalize_embeddings=True).astype(np.float64)
    idx_of = {q: i for i, q in enumerate(all_q)}

    rows = []
    detail = {}
    for name, qs in per_cat.items():
        ids = [idx_of[q] for q in qs]
        E = emb[ids]
        # ★ 카테고리 mean-centering: 공유 단어(자동차/노하우/여행…) 성분 제거 → 하위주제 잔차만
        Ec = E - E.mean(axis=0, keepdims=True)
        nrm = np.linalg.norm(Ec, axis=1, keepdims=True); nrm[nrm < 1e-9] = 1
        Ec = Ec / nrm
        sim = Ec @ Ec.T
        loc = {q: k for k, q in enumerate(qs)}         # 카테고리 로컬 인덱스
        pool_mean = mean_pairwise(sim, list(range(len(qs))))
        sel_local = [loc[q] for q in selected[name]]
        sel_mean = mean_pairwise(sim, sel_local)
        clump = sel_mean - pool_mean                    # ★ threshold-free 핵심 지표

        groups = union_find(sim, UF_THRESHOLD)
        groups.sort(key=len, reverse=True)
        largest_share = len(groups[0]) / len(qs)
        # 현재 4개가 몇 개 그룹에 걸치나
        gid_of = {}
        for gi, g in enumerate(groups):
            for li in g:
                gid_of[li] = gi
        sel_groups = sorted(set(gid_of[li] for li in sel_local))

        rows.append({"category": name, "eligible_n": len(qs),
                     "clump": round(clump, 3), "sel_mean_sim": round(sel_mean, 3),
                     "pool_mean_sim": round(pool_mean, 3),
                     "n_subtopics(T%.2f)" % UF_THRESHOLD: len(groups),
                     "largest_subtopic_share": round(largest_share, 2),
                     "sel_spans_groups": len(sel_groups)})
        detail[name] = {
            "selected": selected[name],
            "subtopics": [[qs[li] for li in g] for g in groups],
        }

    rows.sort(key=lambda r: -r["clump"])   # 쏠림 심한 순
    print("\n=== 하위주제 편중 진단 (clump 높을수록 현재 4개가 뭉침; 쏠림 심한 순) ===")
    print(f"  {'category':<12} {'n':>3} {'clump':>7} {'sel_sim':>7} {'pool_sim':>8} "
          f"{'#sub':>5} {'maxShare':>8} {'4개가걸친그룹':>10}")
    for r in rows:
        print(f"  {r['category']:<12} {r['eligible_n']:>3} {r['clump']:>+7.3f} "
              f"{r['sel_mean_sim']:>7.3f} {r['pool_mean_sim']:>8.3f} "
              f"{r['n_subtopics(T%.2f)' % UF_THRESHOLD]:>5} {r['largest_subtopic_share']:>8.2f} "
              f"{r['sel_spans_groups']:>10}")

    # 쏠림 상위 3개 카테고리의 하위주제 구조 출력
    print("\n=== 쏠림 상위 카테고리 하위주제 구조(참고, T=%.2f) ===" % UF_THRESHOLD)
    for r in rows[:3]:
        name = r["category"]
        print(f"\n[{name}] 현재 선정: {', '.join(detail[name]['selected'])}")
        for gi, g in enumerate(detail[name]["subtopics"]):
            tag = "  (■다수)" if len(g) == max(len(x) for x in detail[name]["subtopics"]) else ""
            print(f"   그룹{gi+1}({len(g)}){tag}: {', '.join(g)}")

    OUT_PATH.write_text(json.dumps({"summary": rows, "detail": detail,
                                    "_meta": {"model": MODEL, "uf_threshold": UF_THRESHOLD,
                                              "note": "DIAGNOSTIC only. 변경 없음."}},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {OUT_PATH} (진단 전용, 아무것도 변경 안 함)")


if __name__ == "__main__":
    main()
