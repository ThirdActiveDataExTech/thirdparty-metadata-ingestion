"""P05 08d — 탐색 심화: Δrank 분포 / α=.7 쿼리별 개선 / category 분산성분. (exploratory)

① Δrank 분포 (관련쌍 전체 + 쿼리별 평균): mean/median/>0·=0·<0 비율/극값
④' category 분산성분(η²): raw gap·영상당 median Δrank가 category로 얼마나 설명되나
⑥ α=.7 vs Text 쿼리별 Recall 변화: 개선/악화 쿼리 목록(+category)
출력: 콘솔. 실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/08d_distributions.py
"""
import csv, importlib.util, json
from collections import defaultdict
from pathlib import Path
import numpy as np

CODE = Path(__file__).resolve().parent; DATA = CODE.parent / "data"
def _load(f,n):
    s=importlib.util.spec_from_file_location(n,CODE/f);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
A7=_load("07_analyze.py","an07")

def eta2(values, groups):
    vals=np.asarray(values,float); g=np.asarray(groups)
    gm=vals.mean(); sst=((vals-gm)**2).sum()
    ssb=sum(len(vals[g==k])*(vals[g==k].mean()-gm)**2 for k in set(g))
    return ssb/sst if sst>0 else float('nan')

def main():
    d=np.load(DATA/"retrieval"/"scores.npz",allow_pickle=True)
    qids=[str(q) for q in d["query_ids"]]; vids=[str(v) for v in d["video_ids"]]; vidx={v:i for i,v in enumerate(vids)}
    text_S,vis_S=d["text_scores"].astype(np.float64),d["visual_scores"].astype(np.float64)
    qrels=json.loads((DATA/"qrels.json").read_text(encoding="utf-8"))
    _qf=json.loads((DATA/"queries_frozen.json").read_text(encoding="utf-8"))["queries"]
    qcat={q["query_id"]:q["category"] for q in _qf}; qtext={q["query_id"]:q["query"] for q in _qf}
    gap={}
    with (DATA/"gap.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f): gap[r["video_id"]]={"cat":r["category"],"raw":float(r["raw_gap"]),"cen":float(r["centered_gap"])}
    qeval=[q for q in qids if q in qrels and any(float(g)>=1 for g in qrels[q].values())]
    def fscore(qi,a): return a*A7._minmax(text_S[qi])+(1-a)*A7._minmax(vis_S[qi])

    # ── ① Δrank 분포 ──
    pair_dr=[]; perq_dr=defaultdict(list); perv=defaultdict(list)
    for q in qeval:
        qi=qids.index(q); rt=A7._ranks(text_S[qi])[0]; rf=A7._ranks(fscore(qi,0.5))[0]
        for v in qrels[q]:
            if float(qrels[q][v])>=1 and v in vidx:
                dr=rt[vidx[v]]-rf[vidx[v]]; pair_dr.append(dr); perq_dr[q].append(dr)
                if v in gap: perv[v].append(dr)
    a=np.array(pair_dr)
    print(f"=== ① Δrank 분포 (rank_text - rank_fusion@.5, 양수=fusion 개선) ===")
    print(f"  관련쌍 n={len(a)} | mean={a.mean():+.2f} median={np.median(a):+.1f} std={a.std():.1f}")
    print(f"  >0(개선) {np.mean(a>0)*100:.1f}% | =0 {np.mean(a==0)*100:.1f}% | <0(악화) {np.mean(a<0)*100:.1f}%")
    print(f"  최대개선 +{a.max()} / 최대악화 {a.min()} | |Δ|<=2 인 비율 {np.mean(np.abs(a)<=2)*100:.1f}%")
    pq=np.array([np.mean(perq_dr[q]) for q in qeval])
    print(f"  쿼리별 평균Δrank: mean={pq.mean():+.2f} median={np.median(pq):+.2f} | 쿼리 >0 {np.mean(pq>0)*100:.0f}% / <0 {np.mean(pq<0)*100:.0f}%")

    # ── ④' category 분산성분(η²) ──
    vl=[v for v in perv if v in gap]
    raw=np.array([gap[v]["raw"] for v in vl]); mdr=np.array([np.median(perv[v]) for v in vl]); cats=[gap[v]["cat"] for v in vl]
    print(f"\n=== ④' category 분산성분 (η² = category가 설명하는 분산 비율) ===")
    print(f"  raw gap의 η²(category) = {eta2(raw,cats):.3f}  | 영상당 median Δrank의 η²(category) = {eta2(mdr,cats):.3f}")
    print("  → 둘 다 높을수록 raw 상관은 category 구성에 크게 영향받음(교란)")

    # ── ⑥ α=.7 vs Text 쿼리별 Recall 변화 ──
    def rec(q,al):
        qi=qids.index(q); order=A7._ranks(fscore(qi,al))[1]
        rel={vidx[v] for v in qrels[q] if float(qrels[q][v])>=1 and v in vidx}
        return A7._recall_at_k(order,rel,10)
    rows=[(q,qcat[q],rec(q,1.0),rec(q,0.7)) for q in qeval]
    rows=[(q,c,t,f,f-t) for (q,c,t,f) in rows]
    up=sorted([r for r in rows if r[4]>1e-9],key=lambda x:-x[4])
    dn=sorted([r for r in rows if r[4]<-1e-9],key=lambda x:x[4])
    print(f"\n=== ⑥ α=.7 vs Text : 쿼리별 Recall@10 변화 (개선 {len(up)} / 악화 {len(dn)} / 동일 {len(rows)-len(up)-len(dn)}) ===")
    print("  [개선 상위]")
    for q,c,t,f,dd in up[:10]: print(f"    +{dd:.2f}  {c:<10} {qtext[q]:<16} ({t:.2f}->{f:.2f})")
    print("  [악화 상위]")
    for q,c,t,f,dd in dn[:6]: print(f"    {dd:.2f}  {c:<10} {qtext[q]:<16} ({t:.2f}->{f:.2f})")
    # 카테고리별 개선 쿼리 집계
    ic=defaultdict(lambda:[0,0])
    for q,c,t,f,dd in rows:
        if dd>1e-9: ic[c][0]+=1
        elif dd<-1e-9: ic[c][1]+=1
    print("  [카테고리별 개선/악화 쿼리 수]")
    for c in sorted(ic): print(f"    {c:<12} +{ic[c][0]} / -{ic[c][1]}")

if __name__=="__main__": main()
