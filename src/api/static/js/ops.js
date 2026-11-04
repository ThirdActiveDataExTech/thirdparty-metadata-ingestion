import {C, api, esc, num, when, show, loading} from "./core.js";

/* ── 수집 관리 (와이즈넛 화면1) ───────────────────────────────── */
async function viewOps(){
  loading();
  const [ov, reg, runs] = await Promise.all([
    api("/v1/console/overview"), api("/v1/console/registry"), api("/v1/console/runs?limit=30")]);
  const w = ov.waiting_on_human;
  const stages = ov.stages.map(s => `
    <div class="stage ${s.key==='review'&&s.count?'alert':''}">
      <div class="l">${esc(s.label)}</div>
      <div class="n">${num(s.count)}<span class="l"> ${esc(s.unit)}</span></div>
      <div class="note">${esc(s.note)}</div></div>`).join("");
  const types = ov.by_type.map(t => `<tr><td>${esc(t.source_type)}</td>
      <td class="num">${num(t.datasets)}</td><td class="num">${num(t.items)}</td></tr>`).join("");
  const driftCols = reg.drift_columns;
  const rows = reg.items.map(r => `<tr>
      <td>${esc(r.title)}<div class="muted" style="font-size:11px">${esc(r.dataset_id)}</div></td>
      <td><span class="pill ${r.status==='active'?'ok':r.status==='error'?'bad':''}">${esc(r.status)}</span></td>
      <td class="num">${num(r.item_count)}</td>
      <td>${when(r.last_collected_at)}</td><td>${when(r.next_collect_at)}</td>
      ${driftCols ? `<td>${r.source_schema_changed_at ? '<span class="pill warn">변경</span> '+when(r.source_schema_changed_at)
          : (r.source_schema_checked_at ? '<span class="pill ok">동일</span>' : '<span class="muted">미검사</span>')}</td>` : ""}
    </tr>`).join("");
  const log = runs.items.map(r => `<tr>
      <td>${when(r.started_at)}</td><td>${esc(r.title ?? r.dataset_id)}</td>
      <td>${esc(r.activity_type)}</td><td class="num">${num(r.rows_affected)}</td>
      <td><span class="pill ${r.status==='success'?'ok':'bad'}">${esc(r.status)}</span></td>
      <td>${esc(r.triggered_by ?? "")}</td></tr>`).join("");
  show(`
    <div class="panel"><h2>수집 현황</h2>
      <div class="sub">단계별 적체와 실행 이력. 와이즈넛 설계 초안 §5.1 화면1에 대응한다.</div>
      <div class="grid stages">${stages}</div></div>

    <div class="panel"><h2>사람이 처리해야 진도가 나가는 것</h2>
      <div class="sub">이 콘솔을 만든 이유다. 아래 셋은 자동으로 끝나지 않는다.</div>
      <table><tbody>
        <tr><td>관계 검토 대기</td><td class="num">${num(w.relations)}건</td>
            <td><a class="link" onclick="C.go('review')">검토 화면 →</a></td></tr>
        <tr><td>분류 추천(사용자 선택 대기)</td><td class="num">${num(w.category_suggestions)}건</td>
            <td class="muted">ADR-020 — 자동 부여하지 않는다</td></tr>
        <tr><td>검색 평가 라벨</td><td class="num">${num(w.labels_done)} / ${num(w.labels_total)}</td>
            <td><a class="link" onclick="C.go('label')">라벨링 화면 →</a></td></tr>
      </tbody></table></div>

    <div class="panel"><h2>소스 유형별</h2>
      <table><thead><tr><th>source_type</th><th class="num">데이터셋</th><th class="num">아이템</th></tr></thead>
      <tbody>${types}</tbody></table></div>

    <div class="panel"><h2>데이터셋 운영 현황</h2>
      <div class="sub">${driftCols ? "원천 스키마 드리프트 감지 결과를 함께 표시한다."
        : "⚠️ 드리프트 컬럼이 아직 없다 — sql/migration_2026_11_04_source_schema_drift.sql 미적용"}</div>
      <div class="scroll"><table><thead><tr><th>데이터셋</th><th>상태</th><th class="num">아이템</th>
        <th>마지막 수집</th><th>다음 예정</th>${driftCols?"<th>원천 스키마</th>":""}</tr></thead>
      <tbody>${rows}</tbody></table></div></div>

    <div class="panel"><h2>실행 이력</h2>
      <div class="sub">상태에 사유를 병기하지 않는다. 사유는 상세로 분리한다(와이즈넛 §5.1).</div>
      <div class="scroll"><table><thead><tr><th>시작</th><th>대상</th><th>작업</th>
        <th class="num">건수</th><th>상태</th><th>실행자</th></tr></thead><tbody>${log}</tbody></table></div></div>`);
}


export {viewOps};
