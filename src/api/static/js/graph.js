import {S, C, api, esc, num, show, loading, drawNav, render} from "./core.js";

/* ── 관계 지도 (와이즈넛 화면5) ───────────────────────────────── */
async function openGraph(id){ S.current = id; S.tab = "graph"; drawNav(); render(); }
async function viewGraph(){
  if(!S.current) return show(`<div class="empty"><b>기준 데이터셋이 필요합니다</b>
      상세 화면에서 ‘관계 지도 보기’를 누르세요.</div>`);
  loading();
  const g = await api(`/v1/console/datasets/${encodeURIComponent(S.current)}/graph?hops=2&per_node=5`);
  const W=900,H=520,CX=W/2,CY=H/2;
  const byHop={}; g.nodes.forEach(n => (byHop[n.hop] ||= []).push(n));
  const pos={};
  Object.entries(byHop).forEach(([h,list]) => list.forEach((n,i) => {
    const r = +h * 185, a = (i/list.length)*2*Math.PI - Math.PI/2;
    pos[n.dataset_id] = +h===0 ? [CX,CY] : [CX+r*Math.cos(a), CY+r*Math.sin(a)];
  }));
  const COLOR={SEMANTICALLY_RELATED:"#1a4fa0", KEYWORD_OVERLAP:"#0f7b6c"};
  const lines = g.edges.filter(e=>pos[e.source_dataset_id]&&pos[e.target_dataset_id]).map(e=>{
    const [x1,y1]=pos[e.source_dataset_id], [x2,y2]=pos[e.target_dataset_id];
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${COLOR[e.relation_type]||"#aab"}"
            stroke-opacity="${e.status==='APPROVED'?0.75:0.3}" stroke-width="${e.hop===1?2:1}"/>`;}).join("");
  const dots = g.nodes.map(n=>{
    const [x,y]=pos[n.dataset_id]; const root = n.hop===0;
    return `<g style="cursor:pointer" onclick="C.openDataset('${esc(n.dataset_id)}')">
      <circle cx="${x}" cy="${y}" r="${root?13:8}" fill="${root?"#1a4fa0":"#6b8fc7"}"/>
      <text x="${x}" y="${y-16}" text-anchor="middle" font-size="11" fill="#1b2430">${esc((n.title||"").slice(0,18))}</text>
      <text x="${x}" y="${y+20}" text-anchor="middle" font-size="9.5" fill="#6b7684">${esc(n.source_type)} · ${num(n.item_count)}</text>
    </g>`;}).join("");
  const tbl = g.edges.map(e=>`<tr><td>${e.hop}</td><td>${esc(e.source_dataset_id)}</td>
      <td>${esc(e.relation_type)}</td><td class="num">${(e.score??0).toFixed(4)}</td>
      <td>${esc(e.target_dataset_id)}</td>
      <td>${esc((e.evidence?.shared_keywords||[]).join(", "))}</td></tr>`).join("");
  show(`
    <div class="panel"><h2>관계 지도</h2>
      <div class="sub">목록으로 표현할 수 없는 <b>다단계 연결</b>이 이 화면의 존재 이유다(와이즈넛 §5.2).
        중심이 기준 데이터셋이고, 거리가 단계 수(hop)다. 흐린 선은 아직 검토 대기(PENDING)다.</div>
      <div class="scroll"><svg width="${W}" height="${H}">${lines}${dots}</svg></div>
      <div>${Object.entries(COLOR).map(([k,v])=>`<span class="chip" style="border-left:9px solid ${v}">${k}</span>`).join("")}</div>
    </div>
    <div class="panel"><h2>관계 목록</h2>
      <div class="sub">색 구분이 어려운 경우를 위해 표를 함께 제공한다(와이즈넛 §5.2).</div>
      <div class="scroll"><table><thead><tr><th>hop</th><th>source</th><th>유형</th>
        <th class="num">점수</th><th>target</th><th>공유 키워드</th></tr></thead><tbody>${tbl}</tbody></table></div></div>`);
}

C.openGraph = openGraph;

export {viewGraph, openGraph};
