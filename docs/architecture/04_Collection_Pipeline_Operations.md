# 04. Collection Pipeline Operations — 운영 중 수집 파이프라인 설계

> **Last Updated:** 2026-07-23
> **Status:** 설계안 (구현 전) — Airflow 도입을 전제로 함
>
> Airflow 도입은 [ADR-007](../adr/007_Airflow_Adoption.md)로 확정됐다
> ([ADR-002](../adr/002_KubernetesCronJob_before_Airflow.md) Superseded). 이 문서는 그
> 확정을 전제로 실제 DAG·등록 흐름·Collector 실행 로직을 다룬다.

---

## 1. 이 문서가 다루는 범위

- 수집 주기에 따른 실제 실행을 Airflow로 어떻게 오케스트레이션할지
- 같은 `source_type` 안에서 새 데이터셋(예: 새 YouTube 채널)이 등장했을 때 무엇을 설정해야 하는지
- 프론트엔드에서 신규 데이터셋 등록 요청(채널 URL, 채널명, API Key, 데이터셋 제목/설명 등)이
  들어왔을 때 백엔드~DB~Airflow까지 전체 흐름 — **소스 타입마다 입력 형태가 다른 문제 포함**
- 등록 이후 정기 수집이 실제로 무엇을 하는지 (Collector 코드 레벨)
- 다루지 않는 것: 완전히 새로운 `source_type`(예: 지금까지 없던 새 플랫폼) 추가 —
  이건 [runbooks/01_Add_New_DataSource.md](../runbooks/01_Add_New_DataSource.md)의 무거운 절차를 따른다
  (신규 `meta_*` 테이블 설계, 신규 Collector 모듈 작성 등). 이 문서는 **기존 source_type
  틀 안에서 데이터셋만 늘어나는 훨씬 가벼운 케이스**를 다룬다.

---

## 2. 핵심 설계 원칙: DB가 스케줄의 단일 진실 공급원(SSOT)

새 데이터셋이 생겨도 Airflow DAG 코드나 K8s 리소스를 건드리지 않아야 한다는 게 이 설계의
핵심 제약이다. 이미 스키마에 이걸 위한 필드가 다 있다:

| 테이블.컬럼 | 역할 |
|---|---|
| `dcat_dataset.source_type` | 어떤 Collector/DAG가 처리할지 결정 |
| `dcat_dataset.subjects` (JSONB) | 실제 수집 대상 목록 (채널 ID, 카테고리 ID, 검색어 등) |
| `data_registry.status` | `pending`/`active`/`paused`/`error` — 이 데이터셋을 지금 수집해야 하는가 |
| `data_registry.next_collect_at` | 다음 수집 예정 시각 — **Airflow가 아니라 DB가 스케줄을 갖는다** |
| `dcat_dataset.accrual_periodicity` | 수집 주기 (ISO 8601: `P1D`, `P7D` 등) |

즉 Airflow DAG는 "지금 몇 시니까 뭘 수집해라"를 스스로 판단하지 않는다. 대신 **주기적으로
`data_registry`를 조회해서 `next_collect_at <= now()`이고 `status='active'`인 데이터셋만
골라 실행**한다. 새 데이터셋은 이 테이블에 행 하나 추가되는 것만으로 다음 스캔 주기에
자동으로 포함된다.

---

## 3. Airflow DAG 설계 — source_type당 1개, Dynamic Task Mapping

### 3.1 구조

```
dags/                              ← 신규 최상위 폴더 (src/와 분리 — Airflow가 스캔하는 경로)
├── collect_video.py               source_type='video' 전용 DAG
├── collect_news.py                source_type='news' 전용 DAG
├── collect_blog.py                source_type='blog' 전용 DAG
├── collect_shopping_insight.py    source_type='shopping_insight' 전용 DAG
├── collect_persona_insight.py     source_type='persona_insight' 전용 DAG
└── common/
    └── registry.py                 data_registry 조회 공통 함수
```

`source_type`당 DAG 1개인 이유: 소스마다 API rate limit, 필요 자격증명, 재시도 정책이
달라 DAG 레벨 설정(동시 실행 수 제한 등)을 분리하는 게 자연스럽다. 데이터셋이 아니라
**source_type 개수만큼만** DAG 파일이 생기므로, source_type이 5~6개인 지금 규모에서
DAG 코드 자체는 자주 안 늘어난다 — 늘어나는 건 각 DAG 안의 동적 task뿐이다.

### 3.2 실행 주체를 3개 레이어로 분해

"Airflow가 수집을 돌린다"는 한 문장으로는 부정확하다. 실제로는 역할이 다른 3개 레이어로
나뉜다 — **"누가 실행하는지"와 "무엇을 판단하는지"와 "실제 작업을 누가 하는지"가 전부
다른 주체다**:

```
[Layer 1] Airflow Scheduler (상시 떠있는 프로세스)
    ↓ DAG의 schedule="*/15 * * * *" 설정에 따라 15분마다 "틱" 발생
    ↓ 매 틱마다 collect_video DAG의 새 DAG Run 시작

[Layer 2] get_due_dataset_ids 태스크 (DAG Run 안의 첫 번째 태스크)
    ↓ 가벼운 DB 쿼리 하나 실행 — "판단"은 여기서 일어남
    ↓ WHERE status IN ('pending','active') AND next_collect_at <= now()
    ↓ 결과: ["dataset_A", "dataset_C"]  (지금 수집해야 할 데이터셋 목록)

[Layer 3] collect_one 태스크 — Layer 2 결과 개수만큼 동적으로 생성됨 (Dynamic Task Mapping)
    ↓ dataset_A 담당 태스크 인스턴스 → src.collectors.youtube.run("dataset_A") 호출
    ↓ dataset_C 담당 태스크 인스턴스 → src.collectors.youtube.run("dataset_C") 호출
    (여기서 실제로 외부 API 호출 + DB 쓰기가 일어남 — Airflow Worker/Executor가 실행)
```

Collector 코드(`src/collectors/*.py`)는 자기가 Airflow에 의해 실행되는지 K8s CronJob에
의해 실행되는지 전혀 모른다 — `run(dataset_id)`이 호출되면 실행될 뿐이다 (ADR-002의
"오케스트레이터 무관" 원칙).

### 3.3 DAG 예시 (video / YouTube)

```python
# dags/collect_video.py
from airflow.decorators import dag, task
from datetime import datetime

@dag(
    dag_id="collect_video",
    schedule="*/15 * * * *",   # 15분마다 "틱" — 실제 수집 여부는 태스크 안에서 판단
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_tasks=5,         # YouTube API rate limit 고려
)
def collect_video_dag():

    @task
    def get_due_dataset_ids() -> list[str]:
        """RUN TIME에 조회 — 방금 등록된 데이터셋도 바로 포함된다."""
        from dags.common.registry import get_due_datasets
        return get_due_datasets(source_type="video")

    @task
    def collect_one(dataset_id: str):
        from src.collectors.youtube import run
        run(dataset_id=dataset_id, triggered_by=f"Airflow collect_video/{dataset_id}")

    collect_one.expand(dataset_id=get_due_dataset_ids())

collect_video_dag()
```

`get_due_dataset_ids`는 **DAG 파싱 시점이 아니라 매 실행(run) 시점**에 조회된다
(Dynamic Task Mapping, Airflow 2.3+). 그래서 15분 틱 사이에 새로 등록된 데이터셋도
다음 틱에서 바로 잡힌다 — DAG 재배포·재파싱을 기다릴 필요가 없다.

### 3.4 데이터셋별로 다른 수집 주기를 어떻게 처리하나

DAG의 `schedule`은 "얼마나 자주 확인할지"(틱 간격)이지 "얼마나 자주 수집할지"가 아니다.
실제 수집 주기는 데이터셋마다 다른 `accrual_periodicity`/`next_collect_at`으로 제어된다.

```
예) YouTube 채널 A: P1D(매일) — 15분 틱마다 확인하다가 next_collect_at 지나면 실행
    YouTube 채널 B: P7D(매주) — 나머지 6일 23시간대 틱에서는 조회는 되지만 skip
```

틱 간격(15분)은 "얼마나 늦게 실행될 수 있는가"의 최대 오차이지, API 호출 횟수를
늘리지 않는다 — `get_due_dataset_ids()`가 걸러낸 것만 실제 태스크로 만들어지므로
수집 대상이 없으면 그 틱엔 아무 태스크도 안 생긴다.

### 3.5 신규 데이터셋이 등록되면 실제로 무슨 일이 일어나는지 (타임라인)

```
10:03 사용자가 프론트엔드에서 새 데이터셋 등록
      → dcat_dataset/data_registry INSERT, next_collect_at = 10:03 (now())
10:03 이 시점 Airflow는 아무것도 모름 — 그냥 DB에 행 하나 추가됐을 뿐

10:15 (다음 15분 틱) Airflow Scheduler가 collect_video DAG 새로 시작
      → get_due_dataset_ids 태스크: SELECT ... WHERE next_collect_at <= now()
      → 방금 등록된 데이터셋도 10:03 <= 10:15라서 결과에 포함됨
      → collect_one 태스크가 이 dataset_id 포함해서 동적 생성
      → run(dataset_id) 호출 → 최초 수집 실행 (§6.1)
      → data_registry.next_collect_at = 10:15 + P1D = 내일 10:15 로 갱신

내일 10:15 다시 틱 → 같은 SQL이 이 dataset_id를 또 골라냄 → 정기 수집 실행 (§6.2)
```

**핵심은 Airflow DAG 코드나 K8s 리소스를 단 한 줄도 안 건드렸다는 점**이다. `data_registry`에
행 하나 추가한 것만으로 다음 틱부터 자동으로 수집 대상이 된다.

---

## 4. 소스 타입별 데이터 형태 차이 — 발견형 vs 선언형

`dcat_dataset.subjects`(JSONB)는 원래 소스마다 다른 형태를 담기 위한 컬럼이다:

```
subjects  JSONB,
-- 예) ["50001421","50000204"]        ← Naver 카테고리 ID
-- 예) ["UCQrLs7LGqlcfrKDM0MXWFCQ"]  ← YouTube 채널 ID
-- 예) ["인공지능","반도체"]           ← 뉴스 검색 키워드
```

하지만 형태만 다른 게 아니라, **"등록 시점에 무엇이 DB에 써지는가"가 소스 타입에 따라
구조적으로 다르다.** 이 차이를 놓치면 등록 API를 하나의 범용 함수로 만들려다가 오히려
꼬인다.

### 4.1 발견형 (YouTube · 뉴스 · 블로그)

사용자가 주는 건 "어디서 찾을지"(채널 ID, 검색어)뿐이다. 실제 아이템(영상/기사/게시물)
목록은 **등록 시점엔 DB에 없고**, Collector가 처음 실행될 때 API를 호출해 "발견"하며
`meta_youtube_video`/`meta_naver_news`/`meta_naver_blog`에 쓴다. 아이템 수는 계속
늘어날 수 있고(새 영상 업로드), 시간이 지나며 일부가 사라질 수도 있다(§6.2 `is_removed`).

### 4.2 선언형 (쇼핑인사이트 · Persona)

`3amd/config.yaml`의 카테고리 목록(`{id, name}` 여러 개)처럼, **목록 자체가 사용자
입력**이다. "발견"할 게 없다 — 사용자가 카테고리를 몇 개 고르면 그게 그대로 **등록
시점에 바로** `meta_naver_shopping`/`meta_naver_persona`에 행으로 들어간다. Collector는
매일 그 고정된 카테고리 목록의 지수만 갱신할 뿐, 새 카테고리를 스스로 찾아내지 않는다.

| | 발견형 (video/news/blog) | 선언형 (shopping/persona) |
|---|---|---|
| 등록 시점에 `meta_*`에 쓰는가 | 아니오 — 최초 Collector 실행 때 | **예 — 등록 API가 직접 씀** |
| 아이템 목록이 늘어나는 방식 | Collector가 매 실행마다 새로 발견 | 사용자가 명시적으로 추가해야만 |
| "삭제 감지"(`is_removed`) 필요 | 필요 (§6.2) | 불필요 — 사용자가 직접 빼기 전까진 그대로 |
| anchor 개념 | 없음 | shopping만 있음 (persona는 없음, §4.3) |
| `meta_*.updated_at`의 의미 | **아이템 자체의 내용**이 바뀐 시각(재스크래핑 등) — 컬럼명은 같아도 카테고리형과 다른 걸 가리킴 | **카테고리 정의**(taxonomy)가 바뀐 시각 — 실제 매일 바뀌는 값은 이 행이 아니라 `active_meta_*` 자식 테이블에 새 행으로 쌓임 |

### 4.3 anchor 카테고리 자동 선택 (shopping_insight 한정)

`meta_naver_shopping.is_anchor`는 데이터셋당 정확히 1개만 있어야 한다(partial unique
index로 DB가 "최대 1개"를 강제). 프론트엔드에서 "이 중 기준 카테고리를 골라주세요"처럼
기술적인 개념을 사용자에게 직접 물어보지 않고, **사용자가 선택한 카테고리 목록 중
첫 번째를 자동으로 anchor로 지정**하는 것으로 결정했다. UX 복잡도를 줄이면서도 제약
조건은 그대로 만족한다.

### 4.4 등록 API의 소스 타입별 핸들러

프론트엔드 폼이 소스별로 다른 것처럼, 백엔드도 소스별로 다른 핸들러 함수를 쓴다 — 하나의
범용 함수로 다 처리하려 하면 오히려 억지스러워진다:

```python
REGISTRATION_HANDLERS = {
    "video":             register_video_dataset,
    "news":              register_news_dataset,
    "blog":              register_blog_dataset,
    "shopping_insight":  register_shopping_dataset,
    "persona_insight":   register_persona_dataset,
}

def register_dataset(payload, caller):
    handler = REGISTRATION_HANDLERS[payload["source_type"]]
    return handler(payload, caller)
```

각 핸들러는 §5.2의 요청 형태를 검증하고, §4.1/§4.2의 차이에 따라 다른 DB 트랜잭션을
실행한다 (§5.3에 shopping_insight 예시).

---

## 5. 신규 데이터셋 등록 흐름 — 프론트엔드 → DB → Airflow

### 5.1 공통 처리 순서

```
1. [프론트엔드] 폼 제출 → 백엔드 API 호출 (POST /api/datasets)
       ↓
2. [백엔드 API] 입력 검증 (소스 타입별 §5.2, 순서는 "비용 적은 것부터")
   a. 필수값 체크 (title/description 등) — 외부 호출 없이 즉시 판별
   b. 소스별 실존 확인 API 호출 (YouTube면 channels.list 등)
      — 이 호출에서 API Key 유효성도 같이 검증되고, 실제 채널명/정규화된 ID도 확보됨
   c. 중복 확인 — 이 caller(owner)가 이미 같은 대상을 등록했는지 (§7.2, owner_id 필요)
       ↓
3. [백엔드 API] DB 트랜잭션 (§4.4 핸들러가 소스 타입별로 다르게 실행, §5.3 예시)
       ↓
4. [Airflow] 아무것도 안 함 — 다음 틱에서 자동으로 주워감 (§3.5)
       ↓
5. [Collector] run(dataset_id=...) 최초 실행 (§6.1)
       ↓
6. [사용자] 프론트엔드에서 상태 변화 확인 (폴링, §7.3)
```

### 5.2 소스 타입별 요청 계약

```jsonc
// video (발견형)
{
  "source_type": "video",
  "title": "경쟁사 반도체 채널 모음", "description": "...",
  "config": { "channel_url": "https://youtube.com/@SamsungSemiconductor" },
  "api_key": "AIzaSy...",              // 선택, 없으면 플랫폼 공유 키 폴백
  "accrual_periodicity": "P1D"          // 선택
}

// news (발견형)
{
  "source_type": "news",
  "title": "...", "description": "...",
  "config": { "keywords": ["인공지능", "반도체"] },
  "api_key": "..."
}

// shopping_insight (선언형)
{
  "source_type": "shopping_insight",
  "title": "...", "description": "...",
  "config": {
    "categories": [
      {"id": "50000148", "name": "식품>음료"},
      {"id": "50007256", "name": "여가/생활편의>해외여행"},
      {"id": "50001102", "name": "스포츠/레저>골프>골프클럽"}
    ]
    // anchor는 categories[0]으로 자동 지정 (§4.3) — 요청에 별도 필드 없음
  },
  "api_key": "..."
}

// persona_insight (선언형, anchor 없음)
{
  "source_type": "persona_insight",
  "title": "...", "description": "...",
  "config": { "categories": [ {"id": "...", "name": "..."}, ... ] },
  "api_key": "..."
}
```

### 5.3 DB 트랜잭션 예시 — shopping_insight (선언형이라 발견형과 다름을 보여줌)

```sql
BEGIN;

INSERT INTO dcat_dataset (dataset_id, title, description, source_type, dataset_origin, subjects)
VALUES ('user_travel_golf_x1', '...', '...', 'shopping_insight', 'user',
        '["50000148","50007256","50001102"]'::jsonb);   -- subjects는 빠른 조회용 요약

INSERT INTO data_registry (dataset_id, status, next_collect_at, pg_meta_table, pg_active_table, vec_collection)
VALUES ('user_travel_golf_x1', 'pending', now(),
        'meta_naver_shopping', 'active_meta_naver_shopping', 'dcat_dataset_vec');

-- 카테고리 3개 → meta_naver_shopping에 즉시 3행 (발견형이었다면 이 단계 자체가 없음)
INSERT INTO meta_naver_shopping (dataset_id, category_id, category_name, is_anchor)
VALUES
  ('user_travel_golf_x1', '50000148', '식품>음료', TRUE),   -- categories[0] → anchor
  ('user_travel_golf_x1', '50007256', '여가/생활편의>해외여행', FALSE),
  ('user_travel_golf_x1', '50001102', '스포츠/레저>골프>골프클럽', FALSE);

COMMIT;
```

video/news/blog(발견형)였다면 `dcat_dataset`+`data_registry`만 쓰고 끝난다 —
`meta_youtube_video` 등은 최초 Collector 실행 때 채워진다 (§5.1의 5번 단계).

### 5.4 "즉시 수집"이 필요하면

15분 틱을 기다리기 싫다면(사용자가 등록 직후 결과를 바로 보고 싶어함), 백엔드 API가
DB 트랜잭션 직후 Airflow REST API로 즉시 DagRun을 트리거할 수 있다:

```python
POST {AIRFLOW_URL}/api/v1/dags/collect_video/dagRuns
{"conf": {"dataset_id": "user_abc123"}}
```

이 경우 DAG를 살짝 손봐야 한다 — `conf`로 특정 dataset_id가 넘어오면 그 하나만,
없으면(정기 틱) `get_due_dataset_ids()`로 전체를 도는 분기가 필요하다. **MVP 범위
결정 필요** (§12) — 15분 이내 자동 반영으로 충분하면 이 트리거 API는 나중으로 미뤄도 된다.

### 5.5 채널명 검증: 사용자 입력 vs API 조회값

사용자가 입력한 "채널명"과 YouTube API가 실제로 반환하는 채널명이 다를 수 있다
(오타, 채널명 변경 등). `dcat_dataset.title`은 **사용자가 입력한 데이터셋 제목**(사람이
관리 목적으로 붙이는 이름)으로 쓰고, API가 반환하는 실제 채널명은
`meta_youtube_video.channel_title`에 수집 시점마다 채워지는 것으로 이미 스키마가
분리되어 있다 — 프론트엔드 UI 문구에서만 이 둘을 구분해주면 된다.

### 5.6 "동일 source_type, 기존 데이터셋에 채널만 추가"하는 경우

새 `dcat_dataset` 행을 만드는 대신, **기존 사용자 데이터셋의 `subjects` 배열에 채널
ID를 추가**하는 경우도 있다 (`dataset_origin='user'`는 원래 "동일 소스 타입 내 복수
채널 자유 조합"을 위해 설계됨). 이 경우:

- `dcat_dataset.subjects` UPDATE만 하면 된다 (`item_count`/`updated_at`도 같이 갱신)
- `data_registry`/Airflow 쪽은 **아무것도 건드릴 필요 없음** — 같은 dataset_id의 다음
  수집 실행 때 Collector가 `subjects`를 다시 읽어서 새 채널도 자동으로 포함
- 프론트엔드에서 "새 컬렉션 만들기"와 "기존 컬렉션에 채널 추가"를 구분된 UX로 제공 권장

### 5.7 admin 경로 = user 경로와 동일 (YAML 불필요)

초기 설계 검토 단계에서 admin(운영팀)이 큐레이션하는 데이터셋은 YAML 파일 + git으로
관리하고 별도 동기화 스크립트로 DB에 반영하는 방식을 고려했었다. **최종적으로는 채택하지
않았다** — §5.1~5.3의 등록 흐름(소스별 핸들러, 검증, 트랜잭션)이 이미 충분히 정리돼
있어서, admin도 **같은 핸들러 함수를 그대로 호출**하면 된다. 차이는 `dataset_origin`
값(`'admin'` vs `'user'`)뿐이다.

YAML+git 동기화를 별도로 유지하지 않는 이유:
- 검증 로직(채널 실존 확인, anchor 자동선택 등)을 두 곳에 중복 구현하면 유지보수 부담이
  커지고 두 경로가 서서히 어긋날 위험이 있다
- YAML의 장점으로 꼽았던 "git 이력을 통한 감사 추적"은 API 호출 로그(누가 언제 무엇을
  요청했는지)로도 동등하게 얻을 수 있다

**보안 주의사항**: `dataset_origin`은 **요청 바디로 받으면 안 된다.** 클라이언트가
`"dataset_origin": "admin"`을 직접 보내면 일반 사용자가 admin 행세를 할 수 있다. 이
값은 인증된 호출자(caller)의 권한(로그인 세션/토큰의 role)을 보고 **서버가 직접 결정**해야
한다.

**대량 등록이 필요하면**: 별도 아키텍처가 아니라, CSV/YAML을 한 줄씩 읽어서 **같은
등록 핸들러를 반복 호출하는 스크립트** 하나면 충분하다. Collector가 파일을 직접 읽는
게 아니라, 스크립트가 파일을 읽어서 결국 같은 API/DB 경로를 타는 것이므로 아키텍처가
늘어나지 않는다.

---

## 6. Collector 실행 로직 — 정기 수집이 실제로 하는 일

`run(dataset_id)`는 **최초 실행이든 정기 실행이든 완전히 같은 함수**다. 별도의 "최초
수집용 코드"가 있는 게 아니라, DB에 이미 뭐가 있는지 보고 함수 하나가 알아서 다르게
동작한다. 두 벌로 나누면 "신규/기존 판단" 로직을 두 곳에 중복 구현해야 해서 어긋날
위험만 커진다.

### 6.1 발견형 소스의 run() — 신규/기존 분기 + 삭제 감지

```python
def run(dataset_id: str, triggered_by: str):
    dataset = fetch_dcat_dataset(dataset_id)
    api_key = get_api_key(dataset_id)          # dataset_credentials 우선, 없으면 플랫폼 키 (§9)
    channel_id = dataset["subjects"]["channel_id"]
    started_at = now()

    try:
        remote_videos = youtube_api.list_channel_videos(channel_id, api_key)
        existing = get_existing_video_ids(dataset_id)   # {video_id: meta_id} — DB에 이미 있는 것
        remote_ids = {v["video_id"] for v in remote_videos}

        new_count, updated_count = 0, 0

        for video in remote_videos:
            if video["video_id"] not in existing:
                # ── 신규 발견: meta 새로 등록 + 첫 스냅샷 (Day 0엔 전부 이 분기)
                meta_id = insert_meta_youtube_video(dataset_id, video)
                insert_active_meta_youtube(meta_id, video["stats"], delta=None)
                new_count += 1
            else:
                # ── 기존 영상: meta는 그대로, 통계만 새 행으로 추가 (시계열 누적)
                meta_id = existing[video["video_id"]]
                prev = get_latest_active_meta(meta_id)
                insert_active_meta_youtube(
                    meta_id, video["stats"],
                    delta_views=video["stats"]["view_count"] - prev["view_count"],
                    delta_likes=video["stats"]["like_count"] - prev["like_count"],
                )
                updated_count += 1

        # ── 삭제 감지: 예전엔 있었는데 이번엔 안 보이는 영상 → is_removed=TRUE
        for video_id, meta_id in existing.items():
            if video_id not in remote_ids:
                mark_removed(meta_id, removed_at=now())

        ended_at = now()
        insert_dcat_provenance(dataset_id, activity_type="update", triggered_by=triggered_by,
                                started_at=started_at, ended_at=ended_at, status="success",
                                rows_affected=new_count + updated_count)
        update_data_registry(
            dataset_id, status="active",
            item_count=len(existing) + new_count,
            last_collected_at=ended_at,
            next_collect_at=ended_at + parse_duration(dataset["accrual_periodicity"]),
        )
    except Exception as e:
        insert_dcat_provenance(dataset_id, status="failure", error_message=str(e))
        update_data_registry(dataset_id, status="error", last_error=str(e),
                              next_collect_at=now() + timedelta(hours=1))  # 재시도 앞당김
        raise
```

`meta_youtube_video`/`meta_naver_news`/`meta_naver_blog`에 `is_removed`/`removed_at`
컬럼을 추가했다 (오늘 반영, §10). 행 자체는 지우지 않고 마지막 known 상태를 보존한다 —
`meta_naver_news`/`meta_naver_blog`도 뉴스와 블로그 API가 정기적으로 같은 검색 결과를
안 돌려줄 수 있으므로 동일한 패턴을 적용했다.

### 6.2 선언형 소스의 run() — 훨씬 단순함

`shopping_insight`/`persona_insight`는 신규/기존 분기도, 삭제 감지도 필요 없다 —
`meta_naver_shopping`의 카테고리 목록은 사용자가 등록 API로 직접 넣은 것이라 Collector가
목록 자체를 바꾸지 않는다. 매 실행마다 그 고정된 카테고리들의 오늘자 지수만 API로
가져와서 `active_meta_naver_shopping`에 새 행을 추가할 뿐이다.

```python
def run(dataset_id: str, triggered_by: str):
    categories = get_meta_naver_shopping_rows(dataset_id)  # 이미 등록된 카테고리 목록
    anchor = next(c for c in categories if c["is_anchor"])
    # ... anchor 기준 intra_scale/inter_scale 계산 (P01 pseudo_volume 방법론과 동일) ...
    for category in categories:
        raw_ratio = shopping_api.get_ratio(category["category_id"], api_key)
        insert_active_meta_naver_shopping(category["id"], raw_ratio, ...)
    # 카테고리 목록 자체는 절대 바꾸지 않음 — 사용자가 subjects UPDATE(§5.6)로만 바꿀 수 있음
```

### 6.3 next_collect_at 갱신과 스케줄 드리프트

`next_collect_at`은 **"이번 수집이 끝난 시각" 기준으로 매번 재계산**한다
(`ended_at + accrual_periodicity`). 즉 정확히 24시간 간격이 보장되는 게 아니라, 수집이
늦어지거나 재시도가 끼면 다음 스케줄도 같이 밀린다(드리프트). "매일 정확히 새벽 2시에"
같은 고정 시각이 필요하면 다른 계산식(다음 지정 시각으로 반올림)이 필요하다 —
**아직 결정 안 됨** (§12).

---

## 7. 동시성·데이터 무결성

### 7.1 dataset_id 채번

`user_` + title을 slugify한 값 + 짧은 랜덤 접미사(예: `user_competitor_semicon_a3f9`).
UUID 하나로 때우는 것보다, `dcat_provenance`/`data_registry`를 사람이 직접
`WHERE dataset_id=...`로 조회하는 일이 이 문서 곳곳에 이미 많아서 읽을 수 있는 식별자가
디버깅에 유리하다. slug 충돌 가능성이 있으니 INSERT가 `unique_violation`나면 접미사를
새로 뽑아 재시도하는 로직이 필요하다.

### 7.2 중복 등록 방지 — owner_id 필요 (§10과 연결)

"이 사용자가 이미 이 채널을 등록했는지" 확인하려면 **누가 등록했는지 알아야 한다.**
`dcat_dataset.owner_id` 컬럼은 추가됐지만(§10, FK는 아직 없음) 아래 조회는 이미 가능하다:

```sql
SELECT dataset_id FROM dcat_dataset
WHERE owner_id = %(owner_id)s AND source_type = %(source_type)s
  AND subjects @> %(channel_id_as_jsonb)s;
```

**완벽한 DB 제약으로 막기는 어렵다** — `subjects`가 JSONB 배열이고 한 데이터셋이
여러 채널을 담을 수 있어서(§5.6), "이 채널이 이미 어딘가에 있는지"는 배열 내부를
봐야 하는 애플리케이션 레벨 체크에 가깝다. 서로 다른 사용자가 같은 공개 채널을 각자
추적하는 건 막을 필요가 없다는 점도 감안해야 한다(그건 정상 케이스).

### 7.3 동시 요청 / 더블클릭

- 더블클릭: 프론트엔드가 제출 버튼을 즉시 비활성화하는 게 1차 방어. 백엔드도 §7.2
  중복 확인이 사실상의 idempotency 역할을 한다.
- 진짜 동시 요청(같은 사용자가 두 탭에서 동시 등록): 검증 통과 후 INSERT 사이에 다른
  요청이 끼어들 수 있다. 완벽히 막으려면 `UNIQUE (owner_id, source_type, ...)` 부분
  인덱스가 필요한데, JSONB 배열 특성상 정확한 구현은 owner_id 확정 후 별도 설계 필요.

### 7.4 최초 수집 실패 시 사용자 경험

등록 API의 §5.1 2-b(채널 실존 확인)는 통과했지만, 실제 최초 수집(§6.1) 단계에서
quota 초과 등으로 실패할 수 있다. 이 경우 `data_registry.status='error'`가 되는데,
프론트엔드는 이걸 "등록 중..." 스피너로 무한정 보여주면 안 되고 **명확한 실패
메시지 + 재시도 버튼**을 노출해야 한다 (§8의 상태 폴링 API가 `status='error'`와
`last_error`를 반환하므로 프론트가 이 상태를 구분해서 렌더링).

---

## 8. 실패 처리 · 재시도 · 모니터링

- **Collector 레벨**: 실패 시 `dcat_provenance.status='failure'` + `error_message` 기록,
  `data_registry.status='error'` + `last_error` 기록, `next_collect_at`은 **당김**(예: 1시간
  후 재시도) — 다음 정기 주기까지 기다리지 않도록.
- **Airflow 레벨**: task 자체의 재시도(`retries=3`, `retry_delay`)는 네트워크 순간 오류
  등 코드 레벨 예외에 대한 것이고, 위 DB 기반 `status='error'` 처리와는 별개 레이어.
  Collector의 `run()`이 예외를 삼키지 않고 그대로 올려야 Airflow 재시도가 의미 있다.
- **최초 수집 실패**: §7.4 참조 — 정기 수집 실패와 구분해서 프론트엔드에 노출해야 함.
- **모니터링**: `data_registry WHERE status='error'` 조회가 사실상의 알림 대시보드
  쿼리. 초기엔 수동 조회, 이후 Slack 알림 등은 별도 과제(ADR-002의 "실패 모니터링
  고도화" 조건과 직결).

---

## 9. API Key 저장 모델 — 결정: 데이터셋별 저장

`05_Secrets_ConfigMaps.md`의 기존 모델은 플랫폼 전체가 K8s Secret 하나(`youtube-api-secret`,
`naver-api-secret`)를 공유하는 구조였다. 사용자가 데이터셋 등록 시 자신의 API Key를
직접 입력하는 것으로 확정했다 — K8s Secret은 사용자 수만큼 동적으로 늘리기엔 부적합해서
(K8s API 호출 필요, Secret 목록 관리 부담) 새 테이블 `sql/dataset_credentials.sql`을
만들어 DB에 암호화 저장하는 방식을 택했다. 이 프로젝트가 기존에도 별도 인프라를
새로 세우기보다 PostgreSQL로 해결해온 기조(ADR-003 pgvector, ADR-004 SeaweedFS 선정
이유 참조)와 일치한다.

### 9.1 저장 방식

- **암호화**: PostgreSQL `pgcrypto` 확장의 `pgp_sym_encrypt`/`pgp_sym_decrypt` (대칭키)
- **대칭키 위치**: DB가 아니라 K8s Secret(`dataset-credentials-encryption-key`)에 별도 보관
  — DB 접근 권한만으로는 평문을 복호화할 수 없도록 계층을 분리
- **테이블 분리 이유**: `dcat_dataset`은 일반 조회·조인이 잦은 테이블이라, 민감정보를
  거기 컬럼으로 두면 API 응답에 실수로 섞여 나갈 위험이 있다. `dataset_credentials`를
  물리적으로 분리하고 이 테이블에 대한 DB 권한을 Collector 실행 계정으로만 좁힌다.
- **Fallback**: `dataset_credentials`에 해당 dataset_id 행이 없으면 Collector는 플랫폼
  공유 키(`youtube-api-secret` 등)로 폴백한다.

실제 서버 DB에서 `pgp_sym_encrypt`→`pgp_sym_decrypt` 라운드트립과, 틀린 키로 복호화 시
정상적으로 실패하는지까지 롤백 트랜잭션으로 검증 완료.

```sql
-- 저장 (데이터셋 등록 API, 파라미터 바인딩 — 암호화 키를 SQL에 직접 쓰지 않음)
INSERT INTO dataset_credentials (dataset_id, credential_type, encrypted_value)
VALUES (%(dataset_id)s, 'youtube_api_key', pgp_sym_encrypt(%(api_key)s, %(enc_key)s));

-- 조회 (Collector 실행 시, 행 없으면 플랫폼 공유 키로 폴백)
SELECT pgp_sym_decrypt(encrypted_value, %(enc_key)s)
FROM dataset_credentials
WHERE dataset_id = %(dataset_id)s AND credential_type = 'youtube_api_key';
```

전체 컬럼 정의는 [sql/dataset_credentials.sql](../../sql/dataset_credentials.sql) 참조.

---

## 10. `dcat_dataset.owner_id` — 결정: 같은 DB 안의 별도 계정 테이블 참조 (FK는 추후)

이번 설계 과정에서 발견된 구조적 공백이었다. 지금 `dataset_origin`은 `'admin'`/`'user'`
두 값뿐이고, **어떤 사용자**가 만들었는지 저장할 컬럼이 없었다 — 없으면 §7.2의 "이 사용자가
이미 등록했는지" 중복 확인이나 "내 데이터셋 목록" 화면 자체를 구현할 방법이 없다.

**결정 (2026-07-23)**:

- 계정/인증 관련 테이블(회원 정보 등)은 metadata-ingestion 팀이 아니라 **플랫폼 쪽 다른
  담당자가 별도로 설계·구현**한다 — 이 저장소는 사용자 신원을 직접 관리하지 않는다
- 다만 완전히 분리된 서비스/DB가 아니라, **지금 쓰는 `datagokr` database 안에 별도
  스키마로 함께 생성될 예정**이다. 그래서 (같은 서버라도 다른 database였다면 불가능했을)
  **진짜 FK 제약을 나중에 걸 수 있다** — Postgres FK는 같은 database 안에서만 가능하고
  스키마가 달라도 무방하기 때문
- `owner_id`에는 계정명(username) 같은 가변 값이 아니라 그 계정 테이블의 **불변 PK**를
  저장한다 (사용자가 아이디를 바꿔도 `owner_id` 참조가 끊기지 않도록)

**지금 반영한 것**: `dcat_dataset.owner_id TEXT` 컬럼 추가, FK 없음, 인덱스만 추가
(`sql/dcat_dataset.sql`, 롤백 트랜잭션 검증 완료). `dataset_origin='admin'`이면 특정
사용자 소유가 아니므로 NULL 허용.

**나중에 확인·반영해야 할 것** (계정 테이블 스펙 확정 후 — 2026-07-23 기준 아직 미정):

- [ ] 계정 테이블이 실제로 같은 `datagokr` database 안에 생기는지 재확인 (지금은 계획 단계)
- [ ] 계정 테이블/스키마명, PK 컬럼명과 타입(TEXT/UUID/BIGINT 등) 확인
- [ ] `owner_id` 컬럼 타입이 PK 타입과 다르면 `ALTER TABLE dcat_dataset ALTER COLUMN
      owner_id TYPE ...`로 맞춤
- [ ] `ALTER TABLE dcat_dataset ADD CONSTRAINT fk_dcat_dataset_owner
      FOREIGN KEY (owner_id) REFERENCES <스키마>.<계정테이블>(<PK컬럼>)`로 FK 추가
- [ ] §7.2의 `UNIQUE(owner_id, source_type, ...)` 중복 방지 제약 설계 착수 가능해짐

이 항목은 `docs/NEXT_STEPS.md` 2-6에서 추적한다.

---

## 11. 프론트엔드-백엔드 API 계약 (초안, `docs/api/`로 승격 필요)

지금 `docs/api/Metadata_API.md`, `Catalog_API.md`는 둘 다 미작성 상태다. 이 문서에서
필요하다고 확인된 엔드포인트만 초벌로 적어둔다 — 실제 스펙 문서화는 별도 작업.

```
POST   /api/datasets                    신규 데이터셋 등록 (§5, 소스 타입별 요청 형태는 §5.2)
PATCH  /api/datasets/{id}/subjects      기존 데이터셋에 채널/키워드 추가 (§5.6)
GET    /api/datasets/{id}/status        수집 상태 조회 (§7.4)
GET    /api/datasets?owner={owner_id}   내 데이터셋 목록 (owner_id 결정 후, §10)
POST   /api/datasets/{id}/collect-now   즉시 수집 트리거 (§5.4, MVP 이후)
```

`GET /api/datasets/{id}/status` 응답 예시:

```jsonc
{
  "status": "pending",       // pending → active(성공) 또는 error(실패)
  "item_count": null,
  "last_collected_at": null,
  "last_error": null,
  "next_collect_at": "2026-07-22T10:15:00+09:00"
}
```

---

## 12. 이 설계를 실행하기 전에 확정해야 할 것 (요약)

- [x] ~~ADR-002 갱신 여부~~ — **결정: Superseded 처리 완료.** [ADR-007](../adr/007_Airflow_Adoption.md)로
      Airflow 도입 확정 기록 완료 (2026-07-23).
- [x] ~~API Key 모델~~ — §9 결정 완료 (데이터셋별 저장, `dataset_credentials` + pgcrypto)
- [x] ~~anchor 카테고리 UX~~ — §4.3 결정 완료 (사용자가 고른 첫 번째 카테고리 자동 지정)
- [x] ~~admin 등록 경로~~ — §5.7 결정 완료 (YAML 불필요, user와 동일 경로 + `dataset_origin` 서버 결정)
- [x] ~~영상/기사/게시물 삭제 감지~~ — §6.1 결정 완료 (`is_removed`/`removed_at`, 행 보존)
- [x] ~~owner_id 모델~~ — §10 결정 완료 (같은 `datagokr` DB 안의 별도 계정 테이블 참조,
      컬럼은 추가했으나 계정 테이블 스펙 미정이라 FK는 추후)
- [x] ~~즉시 수집 트리거 필요 여부~~ — **결정: MVP엔 넣지 않는다.** §5.4, 최대 15분 지연
      감수 — Airflow REST API 트리거는 나중에 필요해지면 추가
- [x] ~~next_collect_at 드리프트 허용 여부~~ — **결정: 드리프트 허용.** §6.3, "수집 종료
      시각 + 주기" 재계산 방식 그대로 유지 — 고정 시각 스케줄이 필요한 다운스트림
      소비자가 없어 계산식 변경 불필요
- [ ] Airflow 자체의 배포 방법 (K8s에 Airflow 설치 방식 — Helm chart, KubernetesExecutor
      여부 등) — 이 문서는 DAG/스케줄 설계만 다루고 Airflow 인프라 자체의 배포는
      다루지 않음. 별도 인프라 문서 필요 (`docs/infrastructure/07_Airflow.md` 후보)

---

## 관련 문서

- 전체 시스템 구조: [01_System_Architecture.md](01_System_Architecture.md)
- 정적 데이터 흐름: [02_Metadata_Flow.md](02_Metadata_Flow.md)
- 모듈 구조: [03_Component_Architecture.md](03_Component_Architecture.md)
- 새 source_type 자체를 추가하는 무거운 절차: [runbooks/01_Add_New_DataSource.md](../runbooks/01_Add_New_DataSource.md)
- 기존 source_type 내 새 데이터셋을 추가하는 가벼운 절차: [runbooks/04_Add_New_Dataset_Existing_Source.md](../runbooks/04_Add_New_Dataset_Existing_Source.md)
- 자격증명 관리: [infrastructure/05_Secrets_ConfigMaps.md](../infrastructure/05_Secrets_ConfigMaps.md)
- CronJob 관련 (이 문서로 사실상 대체됨): [infrastructure/02_Kubernetes.md](../infrastructure/02_Kubernetes.md) §CronJob 운영 계획
- P01 연구 기획서 (pseudo_volume 방법론, §6.2 shopping intra/inter_scale과 동일 개념): [research/research_proposals.md](../research/research_proposals.md)
