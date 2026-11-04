import {C, api, post, esc, num, show, loading} from "./core.js";

/* ── 검토 (와이즈넛 화면2의 우리 버전) ───────────────────────── */
async function viewReview(){
  loading();
  const r = await api("/v1/console/review/relations?status=PENDING&limit=50");
  if(!r.items.length) return show('<div class="empty"><b>검토 대기가 없습니다</b></div>');
  show(`<div class="panel"><h2>관계 검토 — ${num(r.items.length)}건</h2>
    <div class="sub">자동 산출은 <b>확정이 아니다</b>. 근거(evidence)를 보고 사람이 정한다.
      B2를 다시 돌려도 여기서 바꾼 것은 지워지지 않는다.</div>
    ${r.items.map(x=>`<div class="hit" id="rel${x.id}">
      <div class="t">${esc(x.source_title)} <span class="muted">↔</span> ${esc(x.target_title)}</div>
      <div class="m"><span class="pill">${esc(x.relation_type)}</span>
        <span class="pill">점수 ${(x.score??0).toFixed(4)}</span>
        <span class="pill">${esc(x.method)}</span></div>
      <div class="ev">${esc(JSON.stringify(x.evidence))}</div>
      <div style="margin-top:7px">
        <button class="act ok" onclick="C.decide(${x.id},'APPROVED',event)">승인</button>
        <button class="act bad" onclick="C.decide(${x.id},'REJECTED',event)">거부</button></div>
    </div>`).join("")}</div>`);
}
async function decide(id, action, ev){
  ev.stopPropagation();
  await post("/v1/console/review/relations", {id, action});
  const el = document.getElementById("rel"+id);
  el.style.opacity = .4;
  el.querySelector("div[style]").innerHTML =
    `<span class="pill ${action==='APPROVED'?'ok':'bad'}">${action}</span>`;
}

C.decide = decide;

export {viewReview, decide};
