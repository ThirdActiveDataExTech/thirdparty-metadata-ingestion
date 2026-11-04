import {S, C, api, $, esc, num, show, loading, fail, drawNav, render} from "./core.js";

/* ── 데이터 찾기 (와이즈넛 화면3) ─────────────────────────────── */
async function runSearch(){
  const q = $("#q").value.trim(), src = $("#qsrc").value;
  if(!q) return;
  S.tab = "find"; drawNav(); loading();
  try{
    S.lastSearch = await api(`/v1/search?q=${encodeURIComponent(q)}&source=${src}&limit=20&explain=true`);
    render();
  }catch(e){ fail(e); }
}
function viewFind(){
  if(!S.lastSearch) return show(`<div class="empty"><b>검색어를 입력하세요</b>
      벡터·키워드 두 채널을 RRF로 결합합니다(ADR-010). 결과에 두 채널의 순위가 그대로 실립니다.</div>`);
  const r = S.lastSearch, rt = r.rarest_token;
  const hits = r.hits.map(h => `
    <div class="hit" ${r.source==='dataset'?`onclick="C.openDataset('${esc(h.id)}')"`:""}>
      <div class="t">${esc(h.title)}</div>
      <div class="m">${esc(h.subtitle ?? "")}</div>
      <div class="m">
        <span class="pill">RRF ${h.rrf?.toFixed(4) ?? "—"}</span>
        <span class="pill ${h.vec_rank?'ok':''}">벡터 ${h.vec_rank ?? "미검출"}</span>
        <span class="pill ${h.kw_rank?'ok':''}">키워드 ${h.kw_rank ?? "미검출"}</span>
      </div>
      ${h.ai_summary?`<div class="ev">${esc(h.ai_summary)}</div>`:""}
      ${(h.ai_keywords||[]).map(k=>`<span class="chip">${esc(k)}</span>`).join("")}
    </div>`).join("");
  show(`
    <div class="panel">
      <h2>“${esc(r.query)}” 검색 결과 ${num(r.total)}건</h2>
      <div class="sub">소스: ${esc(r.source)} · 형태소: ${r.tokens.map(t=>esc(t)).join(" · ")}</div>
      ${rt ? `<div class="warnbox">최희귀어 <b>${esc(rt.token)}</b> — 문서빈도 ${num(rt.df)}건
        ${rt.absent ? "· <b>이 말이 색인에 전혀 없다. 답이 없을 가능성이 높다</b>(ADR-018)" : ""}</div>` : ""}
      ${hits || '<div class="empty">결과가 없습니다</div>'}
    </div>`);
}


export {viewFind, runSearch};
