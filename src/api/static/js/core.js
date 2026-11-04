export const API = "";
export const TABS = [
  ["find",   "데이터 찾기"],
  ["detail", "데이터셋 상세"],
  ["graph",  "관계 지도"],
  ["bundle", "데이터 합치기"],
  ["review", "검토"],
  ["label",  "라벨링"],
  ["ops",    "수집 관리"],
  ["struct", "정형"],
];
/** 화면 사이에 공유되는 상태. 모듈에는 전역이 없으므로 한 객체에 모은다. */
export const S = {tab:"ops", current:null, lastSearch:null, labelState:null, purpose:null};

/** 생성한 HTML의 `onclick`이 닿을 수 있는 **유일한** 전역. 각 화면이 자기 것만 올린다. */
export const C = {};
window.C = C;

/** 탭 키 → 화면 함수. app.js가 채운다 — core가 화면을 import하면 순환이 된다. */
const SCREENS = {};
export function register(key, fn){ SCREENS[key] = fn; }

export const $ = s => document.querySelector(s);
export const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
export const num = n => (n ?? 0).toLocaleString("ko-KR");
export const when = t => t ? String(t).replace("T"," ").slice(0,16) : "—";
export async function api(p, opt){ const r = await fetch(API+p, opt); if(!r.ok) throw new Error(await r.text()); return r.json(); }
export function post(p, body){ return api(p, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)}); }

export function drawNav(){
  $("#nav").innerHTML = TABS.map(([k,l]) =>
    `<button class="${k===S.tab?'on':''}" data-k="${k}">${l}</button>`).join("");
  $("#nav").querySelectorAll("button").forEach(b =>
    b.onclick = () => { S.tab = b.dataset.k; drawNav(); render(); });
}
export function show(html){ $("#view").innerHTML = html; }
export function loading(){ show('<div class="empty">불러오는 중…</div>'); }
export function fail(e){ show(`<div class="panel"><h2>불러오지 못했습니다</h2><pre class="muted">${esc(e.message)}</pre></div>`); }

export function go(k){ S.tab = k; drawNav(); render(); }

export function render(){
  const f = SCREENS[S.tab];
  if(!f) return fail(new Error(`등록되지 않은 화면: ${S.tab}`));
  try{ const r = f(); if(r && r.catch) r.catch(fail); }catch(e){ fail(e); }
}

C.go = go;

