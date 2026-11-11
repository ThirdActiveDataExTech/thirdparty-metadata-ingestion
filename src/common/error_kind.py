"""수집 실패 원인 분류 — 오류 문구 하나를 받아 **원인·관리자 조치·사용자 안내**로 바꾼다.

## 왜 저장하지 않고 읽을 때 분류하나

`data_registry.last_error`·`dcat_provenance.error_message`에는 원문 오류가 이미 있다.
분류를 따로 저장하면

- 규칙을 고칠 때마다 과거 기록을 다시 써야 하고(안 쓰면 같은 오류가 화면마다 다르게 나온다)
- 파이프라인 5개와 와이즈넛 정형 수집이 모두 같은 형식으로 써야 한다(공유 테이블이라 합의가 필요하다).

읽을 때 분류하면 규칙을 고치는 즉시 과거 기록까지 같은 기준으로 보이고, 와이즈넛이 쓴 오류도
그대로 분류된다. 오류 문구는 수백 건 규모라 매번 정규식을 돌려도 비용이 없다.

## 규칙

2026-11-09 3시간 시험 가동의 감시 스크립트(scratchpad `tick_report.sh`) 7종을 옮겼다.
**위에서부터 먼저 맞는 것**이 이긴다. 순서가 의미를 가진다.

- `db`가 `transient`보다 앞이다. psycopg2의 "could not receive data from server: Operation timed
  out"은 원천 서버가 아니라 **우리 DB** 문제인데, 뒤에 두면 "timed out"에 먼저 걸린다.
- `429`·`401`·`403`·`50x`는 HTTP 맥락에서만 잡는다. 맨 숫자로 잡으면 "반영 429행" 같은 문구에 걸린다.

## 사용자에게 보이는 것

`user_message`만 보인다. 원문 오류에는 내부 주소·호스트·키 일부가 섞일 수 있어 **관리자 화면에만**
낸다(그것도 `config.mask_secrets`를 거쳐서). `user_action`이 참이면 사용자가 직접 고쳐야 하는 것
(예: 본인이 넣은 API 키)이고, 거짓이면 자동 재시도나 관리자 조치로 풀린다.

Pod 자체가 죽는 경우(OOMKilled·시간 초과)는 파이프라인이 오류를 남기기 전에 프로세스가 끝난다.
예전엔 DB에 흔적이 없어 "수집 지연"으로만 드러났다. 2026-11-11부터 스케줄러가 시작할 때 진행 표시를
남기고, 다음 틱이 주인 없는 표시를 `interrupted` 오류로 바꾼다(scripts/scheduler_tick.py).
DB만으로는 죽은 이유(메모리·시간·강제 종료)를 구분할 수 없어 관리자 조치에 확인 방법을 적는다.
"""

import re
from typing import Dict, List, Optional, Tuple

#: (코드, 패턴, 원인, 관리자 조치, 사용자 안내, 사용자가 고칠 일인가)
_HTTP = r"(?:HTTP(?:Error)?\s*|status(?:_code)?\s*[=:]?\s*|Client Error:?\s*|Server Error:?\s*|\(|\b)"
RULES: List[Tuple[str, str, str, str, str, bool]] = [
    # scheduler_tick.INTERRUPTED_PREFIX — 문구를 바꾸면 여기도 같이 바꾼다(tests/test_error_kind.py가 잡는다)
    ("interrupted", r"수집 프로세스가 끝나지 않고 중단되었습니다",
     "실행 중단(메모리 부족 추정)",
     "파드 종료 사유 확인(kubectl describe pod — OOMKilled면 CronJob memory limit 상향 또는 1회 처리 건수 축소, "
     "DeadlineExceeded면 activeDeadlineSeconds 확인). 반복되면 재시도 간격이 1→6→24시간으로 늘어난다",
     "처리 중 서버 자원이 부족해 수집이 중단되었습니다. 관리자가 확인하고 있으며 자동으로 다시 수집합니다", False),
    ("oom", r"OOMKilled|MemoryError|Cannot allocate memory",
     "메모리 부족", "CronJob memory limit 상향 또는 1회 처리 건수 축소",
     "처리 중 서버 자원이 부족했습니다. 관리자가 확인하고 있습니다", False),
    ("quota", r"quotaExceeded|rateLimitExceeded|Too Many Requests|" + _HTTP + r"429\b|호출 한도",
     "API 호출 한도 초과", "한도가 풀리면 자동 재시도. 반복되면 수집 주기·건수 조정",
     "원천 API의 호출 한도를 넘었습니다. 한도가 풀리면 자동으로 다시 수집합니다", False),
    ("auth", r"Unauthorized|Forbidden|API key not valid|invalid[ _-]?(?:api[ _-]?)?key|keyInvalid|"
             r"SignatureDoesNotMatch|AccessDenied|" + _HTTP + r"40[13]\b",
     "인증·키 문제", "Secret 또는 사용자가 등록한 키의 유효성·권한 확인",
     "API 키가 맞지 않거나 권한이 없습니다. 등록한 키를 확인해 주세요", True),
    ("db", r"psycopg2|OperationalError|could not connect to server|server closed the connection",
     "DB 연결", "DB 상태·Secret DB_* 확인",
     "저장소 연결 문제로 수집하지 못했습니다. 관리자가 확인하고 있습니다", False),
    ("storage", r"botocore|EndpointConnectionError|NoSuchBucket|NoSuchKey|\bS3\b",
     "오브젝트 스토리지", "SeaweedFS 상태·Secret S3_* 확인",
     "원본 저장소 문제로 수집하지 못했습니다. 관리자가 확인하고 있습니다", False),
    ("model", r"HF_HUB_OFFLINE|LocalEntryNotFound|huggingface\.co",
     "모델 파일 누락", "이미지에 모델 파일 누락. Dockerfile 확인",
     "분석 모델을 불러오지 못했습니다. 관리자가 확인하고 있습니다", False),
    ("transient", r"timed out|Timeout|ConnectionError|ConnectTimeout|Temporary failure|"
                  r"Max retries|Connection reset|RemoteDisconnected|" + _HTTP + r"50[0234]\b",
     "외부 서버 일시 오류", "조치 불필요 (1시간 후 자동 재시도)",
     "원천 서버 응답이 늦거나 일시적으로 끊겼습니다. 자동으로 다시 수집합니다", False),
]
_COMPILED = [(code, re.compile(pat, re.I), *rest) for code, pat, *rest in RULES]

UNKNOWN = ("unknown", "코드·데이터 오류(미분류)", "로그 Traceback 조사 필요",
           "수집 중 오류가 났습니다. 관리자가 확인하고 있습니다", False)


def classify_error(text: Optional[str]) -> Optional[Dict[str, object]]:
    """오류 문구 → {kind, label, admin_action, user_message, user_action}. 문구가 없으면 None."""
    if not text or not str(text).strip():
        return None
    for code, rx, label, admin, user, user_action in _COMPILED:
        if rx.search(text):
            return {"kind": code, "label": label, "admin_action": admin,
                    "user_message": user, "user_action": user_action}
    code, label, admin, user, user_action = UNKNOWN
    return {"kind": code, "label": label, "admin_action": admin,
            "user_message": user, "user_action": user_action}


def for_user(text: Optional[str]) -> Optional[Dict[str, object]]:
    """사용자 화면용 — 원문 오류를 빼고 안내만 남긴다."""
    c = classify_error(text)
    if c is None:
        return None
    return {"kind": c["kind"], "label": c["label"], "message": c["user_message"],
            "user_action": c["user_action"]}
