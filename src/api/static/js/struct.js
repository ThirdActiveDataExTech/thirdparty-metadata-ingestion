import {show} from "./core.js";

/* ── 정형 (비워 둔다) ─────────────────────────────────────────── */
function viewStruct(){
  show(`<div class="panel"><h2>정형 데이터</h2>
    <div class="empty"><b>아직 들어오지 않았습니다</b>
      <p><code>meta_datagokr_file</code> 0건 · <code>meta_datagokr_file_vec</code> 0건</p>
      <p class="muted" style="max-width:640px;margin:10px auto">
        정형은 data.go.kr 목록 1건이 곧 데이터셋이라 제목·기관·갱신주기·라이선스를 <b>파싱으로 채웁니다.</b>
        비정형은 원천에 ‘데이터셋’이라는 개념이 없어 사람이 정의해야 하고, 그 아래 아이템만 자동으로 찹니다.<br><br>
        저장 형식(<code>vec_role</code>)과 임베딩 모델 규약은 와이즈넛 협의 중입니다.
        합의 전에 화면을 만들면 결과에 따라 다시 만들게 되므로 비워 둡니다.</p>
    </div></div>`);
}


export {viewStruct};
