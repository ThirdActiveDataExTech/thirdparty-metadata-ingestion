"""P05 08f — non-Shorts 민감도 (사전등록 §0.5 Short 강건성). 코퍼스에서 Short 제외 후 재실행.
RQ2: Text vs Fusion@0.5 (MRR/NDCG/Recall@10, Wilcoxon) / RQ1: centered gap ↔ 영상당 median Δrank.
전체 코퍼스 결과와 비교해 결론이 Short 포함에 좌우되지 않는지 확인. 출력: 콘솔.
"""
import csv, importlib.util, json
from collections import defaultdict
from pathlib import Path
import numpy as np

CODE = Path(__file__).resolve().parent; DATA = CODE.parent / "data"
def _load(f,n):
    s=importlib.util.spec_from_file_location(n,CODE/f);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
A7=_load("07_analyze.py","an07")

def run(keep_mask, label):
    d=np.load(DATA/"retrieval"/"scores.npz",allow_pickle=True)
    qids=[str(q) for q in d["query_ids"]]; vids=[str(v) for v in d["video_ids"]]
    text_S=d["text_scores"].astype(np.float64); vis_S=d["visual_scores"].astype(np.float64)
    keep=np.array([keep_mask(v) for v in vids])
    kidx=np.where(keep)[0]; kvids=[vids[i] for i in kidx]
    kvidx={v:j for j,v in enumerate(kvids)}
    qrels=json.loads((DATA/"qrels.json").read_text())
    gap={}
    with (DATA/"gap.csv").open() as f:
        for r in csv.DictReader(f): gap[r["video_id"]]=float(r["centered_gap"])
    def fs(qi,a,S): return a*A7._minmax(text_S[qi][kidx])+(1-a)*A7._minmax(vis_S[qi][kidx])
    def ranks(vec):
        order=np.argsort(-vec); r=np.empty(len(vec),int); r[order]=np.arange(1,len(vec)+1); return r,order
    qeval=[q for q in qids if q in qrels and any(float(g)>=1 and v in kvidx for v,g in qrels[q].items())]
    def perq(q,a):
        qi=qids.index(q); order=ranks(fs(qi,a,None))[1]
        rel={kvidx[v] for v in qrels[q] if float(qrels[q][v])>=1 and v in kvidx}
        grade={kvidx[v]:float(qrels[q][v]) for v in qrels[q] if v in kvidx}
        return A7._rr_at_k(order,rel,10),A7._ndcg_at_k(order,grade,10),A7._recall_at_k(order,rel,10)
    def sysavg(a):
        M=np.array([perq(q,a) for q in qeval]); return M.mean(0)
    T=sysavg(1.0); F=sysavg(0.5)
    # RQ1
    perv=defaultdict(list)
    for q in qeval:
        qi=qids.index(q); rt=ranks(text_S[qi][kidx])[0]; rf=ranks(fs(qi,0.5,None))[0]
        for v in qrels[q]:
            if float(qrels[q][v])>=1 and v in kvidx: perv[v].append(rt[kvidx[v]]-rf[kvidx[v]])
    vl=[v for v in perv if v in gap]
    rho,p=A7._spearman(np.array([gap[v] for v in vl]),np.array([np.median(perv[v]) for v in vl]))
    from scipy.stats import wilcoxon
    tm=[perq(q,1.0)[0] for q in qeval]; fm=[perq(q,0.5)[0] for q in qeval]
    wp=wilcoxon(fm,tm,zero_method="wilcox").pvalue if not np.allclose(np.array(fm)-np.array(tm),0) else 1.0
    print(f"[{label}] 코퍼스 {keep.sum()}편 | 유효쿼리 {len(qeval)} | 영상 {len(vl)}")
    print(f"  Text  MRR {T[0]:.3f} NDCG {T[1]:.3f} Recall {T[2]:.3f}")
    print(f"  Fus.5 MRR {F[0]:.3f} NDCG {F[1]:.3f} Recall {F[2]:.3f} | ΔMRR {F[0]-T[0]:+.3f} Wilcoxon p={wp:.3f}")
    print(f"  RQ1 centered ρ={rho} (p={p})")

sf=json.loads((DATA/"corpus_shorts_flag.json").read_text())
run(lambda v: True, "전체(840)")
run(lambda v: not sf.get(v,False), "non-Shorts")
