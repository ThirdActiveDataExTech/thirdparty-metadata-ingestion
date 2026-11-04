import {S, C, api, post, esc, num, show, loading, render} from "./core.js";

/* ── 라벨링 (대기 #1) ─────────────────────────────────────────── */
async function viewLabel(){
  if(!S.labelState){ loading(); S.labelState = await api("/v1/console/labeling"); S.labelState.i = 0; }
  const st = S.labelState, q = st.queries[st.i];
  if(!q) return show('<div class="empty"><b>채점할 질의가 없습니다</b></div>');
  const pct = st.progress.total ? Math.round(st.progress.done/st.progress.total*100) : 0;
  show(`<div class="panel">
      <h2>검색 평가 라벨링</h2>
      <div class="sub">질의 ${st.i+1} / ${st.queries.length} · 전체 ${num(st.progress.done)} / ${num(st.progress.total)}건 (${pct}%)
        — 이게 끝나야 C1 완료 판정이 됩니다.</div>
      <div class="bar"><i style="width:${pct}%"></i></div>
      <div style="margin:12px 0"><b style="font-size:16px">${esc(q.query)}</b>
        <span class="muted">(${esc(q.query_id)})</span></div>
      ${q.candidates.map(c=>`<div class="hit" style="cursor:default">
        <div class="t">${esc(c.title)}</div>
        <div class="m">${esc(c.doc_id)}</div>
        <div style="margin-top:5px">
          ${[0,1,2].map(g=>`<button class="act ${c.grade===g?'sel':''}"
             onclick="C.grade('${esc(q.query_id)}','${esc(c.doc_id)}',${g},this)">${g}</button>`).join(" ")}
          <span class="muted" style="margin-left:8px">0 무관 · 1 부분 · 2 적합</span>
        </div></div>`).join("")}
      <div style="margin-top:12px">
        <button class="act" onclick="C.moveQ(-1)">← 이전</button>
        <button class="act" onclick="C.moveQ(1)">다음 →</button></div>
    </div>`);
}
function moveQ(d){ S.labelState.i = Math.max(0, Math.min(S.labelState.queries.length-1, S.labelState.i+d)); render(); }
async function grade(query_id, doc_id, g, btn){
  const res = await post("/v1/console/labeling", {query_id, doc_id, grade:g});
  S.labelState.progress = res.progress;
  const q = S.labelState.queries.find(x=>x.query_id===query_id);
  q.candidates.find(c=>String(c.doc_id)===String(doc_id)).grade = g;
  btn.parentElement.querySelectorAll("button").forEach(b=>b.classList.remove("sel"));
  btn.classList.add("sel");
}

C.grade = grade;
C.moveQ = moveQ;

export {viewLabel, grade, moveQ};
