"""P05 08e — Top-10 진입/이탈 + 순위구간별 Δrank + 쿼리 median 분포 (exploratory).

A. Text vs Fusion@.5: relevant의 Top-10 진입/이탈 수, 첫 relevant 순위 변화(=MRR 설명)
B. 구간별(Text rank 1-10/11-50/51-100/101+) Δrank 분포
D. 쿼리 median Δrank: median/IQR/양·음 비율
C(α curve)는 07의 alpha_sensitivity 재출력.
실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/08e_top10_bands.py
"""
import csv, importlib.util, json
from collections import defaultdict
from pathlib import Path
import numpy as np

CODE=Path(__file__).resolve().parent; DATA=CODE.parent/"data"
def _load(f,n):
    s=importlib.util.spec_from_file_location(n,CODE/f);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
A7=_load("07_analyze.py","an07")

def main():
    d=np.load(DATA/"retrieval"/"scores.npz",allow_pickle=True)
    qids=[str(q) for q in d["query_ids"]]; vids=[str(v) for v in d["video_ids"]]; vidx={v:i for i,v in enumerate(vids)}
    text_S,vis_S=d["text_scores"].astype(np.float64),d["visual_scores"].astype(np.float64)
    qrels=json.loads((DATA/"qrels.json").read_text(encoding="utf-8"))
    qeval=[q for q in qids if q in qrels and any(float(g)>=1 for g in qrels[q].values())]
    def fscore(qi,a): return a*A7._minmax(text_S[qi])+(1-a)*A7._minmax(vis_S[qi])

    entered=exited=stay_in=stay_out=0
    first_better=first_worse=first_same=0
    both_top10_first_better=both_top10_first_worse=both_top10_first_same=0
    band_dr=defaultdict(list); perq_med=[]
    def band(r): return "1-10" if r<=10 else "11-50" if r<=50 else "51-100" if r<=100 else "101+"
    for q in qeval:
        qi=qids.index(q); rt=A7._ranks(text_S[qi])[0]; rf=A7._ranks(fscore(qi,0.5))[0]
        rel=[v for v in qrels[q] if float(qrels[q][v])>=1 and v in vidx]
        drs=[]
        for v in rel:
            a,b=rt[vidx[v]],rf[vidx[v]]; drs.append(a-b)
            if a>10 and b<=10: entered+=1
            elif a<=10 and b>10: exited+=1
            elif a<=10 and b<=10: stay_in+=1
            else: stay_out+=1
            band_dr[band(a)].append(a-b)
        perq_med.append(np.median(drs))
        ft=min(rt[vidx[v]] for v in rel); ff=min(rf[vidx[v]] for v in rel)  # 첫 relevant 순위(전체)
        if ff<ft: first_better+=1
        elif ff>ft: first_worse+=1
        else: first_same+=1
        if ft<=10 and ff<=10:  # 둘 다 top10에 첫 relevant 존재(MRR 직접 관련)
            if ff<ft: both_top10_first_better+=1
            elif ff>ft: both_top10_first_worse+=1
            else: both_top10_first_same+=1

    print("=== A. Top-10 진입/이탈 (relevant 단위, Text→Fusion@.5) ===")
    print(f"  진입(밖→Top10): {entered} | 이탈(Top10→밖): {exited} | Top10 유지: {stay_in} | 밖 유지: {stay_out}")
    print(f"  순 진입 = {entered-exited:+d}")
    print("\n=== A'. 첫 relevant 순위 변화 (전체 코퍼스 기준, =MRR 민감축) ===")
    print(f"  전체 쿼리: 개선 {first_better} / 악화 {first_worse} / 동일 {first_same}")
    print(f"  '둘 다 첫 relevant가 Top10' 인 쿼리에서: 개선 {both_top10_first_better} / 악화 {both_top10_first_worse} / 동일 {both_top10_first_same}")
    print("   → 이 부분이 MRR@10을 직접 좌우함")

    print("\n=== B. Text 순위 구간별 Δrank (양수=fusion이 위로 올림) ===")
    print(f"  {'구간':>7} {'n':>5} {'median':>8} {'mean':>8} {'>0비율':>8}")
    for bd in ["1-10","11-50","51-100","101+"]:
        x=np.array(band_dr[bd]) if band_dr[bd] else np.array([0])
        print(f"  {bd:>7} {len(band_dr[bd]):>5} {np.median(x):>8.1f} {x.mean():>8.1f} {np.mean(x>0)*100:>7.0f}%")

    print("\n=== D. 쿼리 median Δrank 분포 (63쿼리, inferential 단위) ===")
    pm=np.array(perq_med)
    print(f"  median={np.median(pm):+.1f} | IQR=[{np.percentile(pm,25):+.1f}, {np.percentile(pm,75):+.1f}] | 양수 {np.mean(pm>0)*100:.0f}% / 0 {np.mean(pm==0)*100:.0f}% / 음수 {np.mean(pm<0)*100:.0f}%")

    print("\n=== C. α curve (07 재확인) ===")
    a=json.loads((DATA/"analysis_results.json").read_text())["alpha_sensitivity"]
    print(f"  {'α':>4} {'MRR':>7} {'NDCG':>7} {'Recall':>7}")
    for k in sorted(a,key=float):
        if float(k) in (0.5,0.6,0.7,0.8,0.9,1.0):
            v=a[k]; print(f"  {k:>4} {v['MRR@10']:>7.3f} {v['NDCG@10']:>7.3f} {v['Recall@10']:>7.3f}")

if __name__=="__main__": main()
