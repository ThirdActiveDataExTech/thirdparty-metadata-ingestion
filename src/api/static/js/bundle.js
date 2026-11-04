import {S, C, api, $, esc, show} from "./core.js";

/* ── 데이터 합치기 = C2 활용 목적 묶음 ───────────────────────── */
async function viewBundle(){
  const purpose = (S.purpose ?? "");
  show(`<div class="panel"><h2>데이터 합치기 — 활용 목적 묶음</h2>
    <div class="sub">검색어가 아니라 <b>하고 싶은 일</b>을 적는다. 검색으로 씨앗을 찾고 관계로 넓힌 뒤
      순위로 합친다(C2). 왜 묶였는지가 각 항목에 붙는다.</div>
    <form onsubmit="C.doBundle(event)" style="display:flex;gap:6px;margin-bottom:12px">
      <input id="purpose" style="flex:1;padding:8px;border:1px solid var(--line);border-radius:4px"
             value="${esc(purpose||"전기차 충전 인프라 수요를 분석하고 싶다")}">
      <button class="act" type="submit">묶기</button></form>
    <div id="bundleOut"></div></div>`);
}
async function doBundle(ev){
  ev.preventDefault();
  const p = $("#purpose").value.trim(); S.purpose = p;
  $("#bundleOut").innerHTML = '<div class="empty">묶는 중…</div>';
  const b = await api(`/v1/discover?purpose=${encodeURIComponent(p)}&top_k=10`);
  $("#bundleOut").innerHTML = (b.note?`<div class="warnbox">${esc(b.note)}</div>`:"") +
    (b.bundle.length ? b.bundle.map(x=>`
      <div class="hit" onclick="C.openDataset('${esc(x.dataset_id)}')">
        <div class="t">${esc(x.title)}</div>
        <div class="m"><span class="pill">${x.score.toFixed(4)}</span>
          <span class="pill ${x.reached_by==='both'?'ok':''}">${esc(x.reached_by)}</span></div>
        <div class="ev">${esc(x.why)}</div></div>`).join("")
      : '<div class="empty">묶인 데이터셋이 없습니다</div>');
}

C.doBundle = doBundle;

export {viewBundle, doBundle};
