"""P05 09 — 논문 그림 생성.
  그림 2: 융합 가중치 α별 성능 (α curve; α=1은 text-only, 1-α=시각 비중)
  그림 3: centered gap vs 영상당 median Δrank 산점도 (ρ≈0)
출력: results/fig2_alpha_curve.png, results/fig3_gap_scatter.png (300dpi)
실행: PYTHONPATH=. .venv/bin/python docs/research/P05_thumbnail_fusion/code/09_figures.py
"""
import csv, importlib.util, json
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CODE = Path(__file__).resolve().parent; DATA = CODE.parent / "data"; RES = CODE.parent / "results"
def _load(f,n):
    s=importlib.util.spec_from_file_location(n,CODE/f);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
A7=_load("07_analyze.py","an07")
plt.rcParams.update({"font.size":11,"axes.grid":True,"grid.alpha":0.3,"figure.dpi":300})

# ── 그림 2: α curve ──
a=json.loads((DATA/"analysis_results.json").read_text())["alpha_sensitivity"]
xs=sorted(float(k) for k in a)
mrr=[a[f"{x:.1f}" if f"{x:.1f}" in a else str(x)]["MRR@10"] for x in xs]
def gv(x,m):
    k=f"{x:.1f}" if f"{x:.1f}" in a else str(x); return a[k][m]
mrr=[gv(x,"MRR@10") for x in xs]; ndcg=[gv(x,"NDCG@10") for x in xs]; rec=[gv(x,"Recall@10") for x in xs]
fig,ax=plt.subplots(figsize=(5.2,3.4))
ax.plot(xs,mrr,"-o",ms=4,label="MRR@10")
ax.plot(xs,ndcg,"-s",ms=4,label="NDCG@10")
ax.plot(xs,rec,"-^",ms=4,label="Recall@10")
ax.axvline(0.5,color="gray",ls="--",lw=0.8); ax.text(0.5,ax.get_ylim()[0],"  preregistered\n  (α=0.5)",va="bottom",ha="left",fontsize=8,color="gray")
ax.set_xlabel(r"$\alpha$  (weight on text; visual weight = 1$-\alpha$)")
ax.set_ylabel("Score"); ax.set_xlim(-0.02,1.02); ax.legend(loc="lower right",fontsize=9)
fig.tight_layout(); fig.savefig(RES/"fig2_alpha_curve.png"); plt.close(fig)

# ── 그림 3: gap scatter ──
d=np.load(DATA/"retrieval"/"scores.npz",allow_pickle=True)
qids=[str(q) for q in d["query_ids"]]; vids=[str(v) for v in d["video_ids"]]; vidx={v:i for i,v in enumerate(vids)}
text_S,vis_S=d["text_scores"].astype(np.float64),d["visual_scores"].astype(np.float64)
qrels=json.loads((DATA/"qrels.json").read_text())
gap={}
with (DATA/"gap.csv").open() as f:
    for r in csv.DictReader(f): gap[r["video_id"]]=float(r["centered_gap"])
def fscore(qi,al): return al*A7._minmax(text_S[qi])+(1-al)*A7._minmax(vis_S[qi])
qeval=[q for q in qids if q in qrels and any(float(g)>=1 for g in qrels[q].values())]
perv=defaultdict(list)
for q in qeval:
    qi=qids.index(q); rt=A7._ranks(text_S[qi])[0]; rf=A7._ranks(fscore(qi,0.5))[0]
    for v in qrels[q]:
        if float(qrels[q][v])>=1 and v in vidx: perv[v].append(rt[vidx[v]]-rf[vidx[v]])
vl=[v for v in perv if v in gap]
gx=np.array([gap[v] for v in vl]); gy=np.array([np.median(perv[v]) for v in vl])
rho,p=A7._spearman(gx,gy)
fig,ax=plt.subplots(figsize=(5.2,3.4))
ax.scatter(gx,gy,s=14,alpha=0.45,edgecolor="none",color="#5b9bd5")
ax.axhline(0,color="gray",lw=0.7)
# gap 5분위 구간별 median (중심경향; OLS 대신 이상치에 강건)
qedges=np.quantile(gx,np.linspace(0,1,6))
cx,cy=[],[]
for i in range(5):
    m=(gx>=qedges[i])&(gx<=qedges[i+1]) if i==4 else (gx>=qedges[i])&(gx<qedges[i+1])
    if m.sum(): cx.append(gx[m].mean()); cy.append(np.median(gy[m]))
ax.plot(cx,cy,"-o",color="crimson",lw=1.4,ms=5,label="binned median (gap quintiles)")
ax.set_xlabel("centered gap  (thumbnail–title)"); ax.set_ylabel(r"per-video median $\Delta$rank")
ax.set_ylim(-140,680)
ax.annotate(f"Spearman ρ = {rho:.2f} (n.s.)", xy=(0.03,0.93), xycoords="axes fraction", fontsize=9)
ax.legend(loc="upper right",fontsize=8)
fig.tight_layout(); fig.savefig(RES/"fig3_gap_scatter.png"); plt.close(fig)

print("저장:", RES/"fig2_alpha_curve.png", "|", RES/"fig3_gap_scatter.png", f"(n={len(vl)}, ρ={rho})")
