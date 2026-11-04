import {S, C, api, esc, num, show, loading, drawNav, render} from "./core.js";

/* ── 데이터셋 상세 (와이즈넛 화면4) ───────────────────────────── */
async function openDataset(id){ S.current = id; S.tab = "detail"; drawNav(); render(); }
async function viewDetail(){
  if(!S.current) return show(`<div class="empty"><b>데이터셋을 고르세요</b>
      '데이터 찾기'에서 소스를 <b>데이터셋</b>으로 두고 검색한 뒤 결과를 누르면 열립니다.</div>`);
  loading();
  const [d, f, it] = await Promise.all([
    api(`/v1/datasets/${encodeURIComponent(S.current)}`),
    api(`/v1/console/datasets/${encodeURIComponent(S.current)}/features`),
    api(`/v1/console/datasets/${encodeURIComponent(S.current)}/items?limit=10`)]);
  const feat = Object.fromEntries(f.items.map(x => [x.feature_name, x.value]));
  const kw = (feat.top_keywords||[]).map(k => `<span class="chip t">${esc(k.term||k)}</span>`).join("");
  const rep = (feat.representative_text||[]).map(t => `<li>${esc(t)}</li>`).join("");
  const sug = (feat.suggested_category||[]).map(c =>
      `<button class="act">${esc(c.name||c.category||JSON.stringify(c))}</button>`).join(" ");
  const prev = it.items.length ? `<div class="scroll"><table><thead><tr>${
      it.columns.map(c=>`<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${
      it.items.map(row=>`<tr>${it.columns.map(c=>`<td>${esc(String(row[c]??"")).slice(0,90)}</td>`).join("")}</tr>`).join("")
    }</tbody></table></div>` : `<div class="empty">${esc(it.reason||"아이템이 없습니다")}</div>`;
  const byType = {};
  (d.relations||[]).forEach(r => (byType[r.relation_type] ||= []).push(r));
  const rels = Object.entries(byType).map(([t, arr]) => `
      <div style="margin-bottom:10px"><b>${esc(t)}</b>
      ${arr.map(r=>`<div class="hit" onclick="C.openDataset('${esc(r.target_dataset_id||r.dataset_id)}')">
        <div class="t">${esc(r.title||r.target_dataset_id)}</div>
        <div class="m"><span class="pill">${(r.score??0).toFixed(4)}</span>
        ${r.status?`<span class="pill ${r.status==='APPROVED'?'ok':'warn'}">${esc(r.status)}</span>`:""}
        ${(r.evidence?.shared_keywords||[]).slice(0,6).map(k=>`<span class="chip">${esc(k)}</span>`).join("")}
        </div></div>`).join("")}</div>`).join("")
    || '<div class="empty">연관 데이터셋이 없습니다</div>';
  show(`
    <div class="panel"><h2>${esc(d.title)}</h2>
      <div class="sub">${esc(d.dataset_id)}</div>
      <p>${esc(d.description||"")}</p>
      <table><tbody>
        <tr><th>제공기관</th><td>${esc(d.publisher)}</td><th>원천</th><td>${esc(d.source)}</td></tr>
        <tr><th>소스 유형</th><td>${esc(d.source_type)}</td><th>아이템</th><td>${num(d.item_count)}</td></tr>
        <tr><th>수록 기간</th><td>${esc(d.temporal_start??"—")} ~ ${esc(d.temporal_end??"진행 중")}</td>
            <th>라이선스</th><td>${esc(d.license??"—")}</td></tr>
      </tbody></table>
      <div style="margin-top:8px">${(d.keywords||[]).map(k=>`<span class="chip">${esc(k)}</span>`).join("")}</div>
      <div style="margin-top:10px"><button class="act" onclick="C.openGraph('${esc(d.dataset_id)}')">관계 지도 보기 →</button></div>
    </div>

    <div class="two">
      <div class="panel"><h2>B1 특징</h2>
        <div class="sub">등록 메타가 아니라 <b>아이템에서 역산한</b> 것이다 — 설명이 평균 28자라 그대로는 못 쓴다.</div>
        <div>${kw || '<span class="muted">키워드 없음</span>'}</div>
        ${rep?`<div class="sub" style="margin-top:10px">대표 문장</div><ul>${rep}</ul>`:""}
        ${sug?`<div class="sub" style="margin-top:10px">분류 추천 — 사용자가 고른다(ADR-020)</div>${sug}`:""}
      </div>
      <div class="panel"><h2>연관 데이터셋</h2>
        <div class="sub">관계 유형별로 묶어 제시한다(와이즈넛 §5.2 화면4).</div>${rels}</div>
    </div>

    <div class="panel"><h2>데이터 미리보기</h2>
      <div class="sub">${it.table ? esc(it.table)+" 상위 10건" : ""}</div>${prev}</div>`);
}

C.openDataset = openDataset;

export {viewDetail, openDataset};
