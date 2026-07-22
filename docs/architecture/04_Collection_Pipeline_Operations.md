# 04. Collection Pipeline Operations — 운영 중 수집 파이프라인 설계

> **Last Updated:** 2026-07-22
> **Status:** 설계안 (구현 전) — Airflow 도입을 전제로 함
>
> ⚠️ **ADR-002("Airflow 도입 전 K8s CronJob 사용")와의 관계**: ADR-002는 "데이터 소스
> 10개 이상 / 단계별 재실행 필요 / 실패 모니터링 고도화 필요" 중 하나라도 충족 시
> Airflow를 도입한다고 규정한다. 이 문서가 다루는 "프론트엔드에서 새 데이터셋이 동적으로
> 등록되면 자동으로 수집 스케줄이 생겨야 한다"는 요구사항은 **정적 K8s CronJob YAML로는
> 구조적으로 불가능**하다(데이터셋마다 YAML 작성 + 재배포 필요). 이는 ADR-002의 "단계별
> 재실행 필요" 조건과도 맞물려 있어, 사실상 Airflow 도입 조건이 충족된 것으로 판단하고
> 이 문서를 작성한다. **다만 ADR-002 자체를 이 문서가 대체하지는 않는다 — 실제 착수 전
> ADR-002를 갱신하거나 새 ADR로 override할 것을 권장한다** (§8 참조).

---

## 1. 이 문서가 다루는 범위

- 수집 주기에 따른 실제 실행을 Airflow로 어떻게 오케스트레이션할지
- 같은 `source_type` 안에서 새 데이터셋(예: 새 YouTube 채널)이 등장했을 때 무엇을 설정해야 하는지
- 프론트엔드에서 신규 데이터셋 등록 요청(채널 URL, 채널명, API Key, 데이터셋 제목/설명 등)이
  들어왔을 때 백엔드~DB~Airflow까지 전체 흐름
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

### 3.2 DAG 예시 (video / YouTube)

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

- `get_due_dataset_ids`는 **DAG 파싱 시점이 아니라 매 실행(run) 시점**에 조회된다
  (Dynamic Task Mapping, Airflow 2.3+). 그래서 15분 틱 사이에 새로 등록된 데이터셋도
  다음 틱에서 바로 잡힌다 — DAG 재배포·재파싱을 기다릴 필요가 없다.
- `run(dataset_id=...)`는 기존 ADR-002 설계 원칙 그대로 — Collector가 `run()` 함수를
  노출하고 DAG는 그걸 얇게 호출만 한다. **Collector 코드 자체는 오케스트레이터를 모른다.**
- 실제 "이 데이터셋이 지금 수집 대상인가"는 `get_due_datasets()` 내부에서
  `WHERE status='active' AND next_collect_at <= now()`로 판단한다 (§4).

### 3.3 데이터셋별로 다른 수집 주기를 어떻게 처리하나

DAG의 `schedule`은 "얼마나 자주 확인할지"(틱 간격)이지 "얼마나 자주 수집할지"가 아니다.
실제 수집 주기는 데이터셋마다 다른 `accrual_periodicity`/`next_collect_at`으로 제어된다.

```
예) YouTube 채널 A: P1D(매일) — 15분 틱마다 확인하다가 next_collect_at 지나면 실행
    YouTube 채널 B: P7D(매주) — 나머지 6일 23시간대 틱에서는 조회는 되지만 skip
```

틱 간격(15분)은 "얼마나 늦게 실행될 수 있는가"의 최대 오차이지, API 호출 횟수를
늘리지 않는다 — `get_due_dataset_ids()`가 걸러낸 것만 실제 태스크로 만들어지므로
수집 대상이 없으면 그 틱엔 아무 태스크도 안 생긴다.

### 3.4 수집 성공 후 next_collect_at 갱신

```python
# src/collectors/youtube.py 의 run() 내부, 성공 시
UPDATE data_registry
SET last_collected_at = now(),
    next_collect_at = now() + (dcat_dataset.accrual_periodicity 파싱값),
    status = 'active',
    row_count = row_count + 이번 실행 rows_affected,
    last_error = NULL
WHERE dataset_id = %s;
```

이 갱신 로직은 Collector 쪽 공통 유틸(`src/common/registry.py` 등)로 묶어서 모든
Collector가 동일하게 쓰도록 한다 (ADR-002가 이미 "각 Collector는 `dcat_provenance` INSERT
로직 포함"이라고 규정한 것과 같은 위치에 추가).

---

## 4. 신규 데이터셋 등록 흐름 — 프론트엔드 → DB → Airflow

### 4.1 시나리오: 사용자가 프론트엔드에서 새 YouTube 채널을 추가

입력 필드 (요청하신 예시 기준):

| 필드 | 목적지 | 비고 |
|---|---|---|
| YouTube 채널 URL/ID | `dcat_dataset.subjects` (JSONB 배열) | 채널 ID로 정규화해서 저장 |
| 채널명 | `dcat_dataset.title` 또는 `subjects` 내 메타 | 사용자 입력 그대로 vs API로 검증된 채널명 중 택1 (§4.4) |
| API Key | **별도 결정 필요** (§6) | 플랫폼 공유 키를 쓸지, 사용자가 직접 낸 키를 쓸지 |
| 데이터셋 제목 | `dcat_dataset.title` | NOT NULL |
| 데이터셋 설명 | `dcat_dataset.description` | NOT NULL (최근 제약 추가됨) |
| (선택) 수집 주기 | `dcat_dataset.accrual_periodicity` | 미입력 시 source_type별 기본값 |

### 4.2 처리 순서

```
1. [프론트엔드] 폼 제출 → 백엔드 API 호출 (예: POST /api/datasets)
       ↓
2. [백엔드 API] 입력 검증
   - channel URL/ID → YouTube Data API로 실존 채널인지 확인 (여기서 API Key 사용)
   - title/description 필수값 확인
   - 같은 채널을 이미 이 사용자가 등록했는지 중복 확인
       ↓
3. [백엔드 API] DB 트랜잭션으로 3개 행 생성
   a. dcat_dataset INSERT
      - dataset_id: 새로 채번 (예: 'user_{uuid}' 또는 slug 기반)
      - source_type: 'video' (프론트에서 이미 소스 선택했으므로 고정)
      - dataset_origin: 'user'
      - subjects: ["채널ID"]
      - item_count: NULL (아직 수집 전이라 모름 — 최초 수집 후 채워짐)
   b. data_registry INSERT
      - status: 'pending'
      - next_collect_at: now() (즉시 수집 대상으로 등록)
      - pg_meta_table/pg_active_table/vec_collection: source_type='video'이므로
        'meta_youtube_video'/'active_meta_youtube'/'dcat_dataset_vec' 고정값
   c. `dataset_credentials` INSERT — 사용자가 입력한 API Key를 `pgp_sym_encrypt`로
      암호화해 저장 (§6 결정 완료, 데이터셋별 저장으로 확정)
       ↓
4. [Airflow] 아무것도 안 함 — 다음 15분 틱에서 collect_video DAG의
   get_due_dataset_ids()가 이 데이터셋을 자동으로 주워감 (status='pending'도
   조회 대상에 포함시켜야 함, §4.3)
       ↓
5. [Collector] run(dataset_id=...) 최초 실행
   - dcat_provenance INSERT (activity_type='initial')
   - meta_youtube_video에 영상 메타 INSERT
   - data_registry UPDATE (status='active', item_count=실제 영상 수, next_collect_at 갱신)
       ↓
6. [사용자] 프론트엔드에서 "수집 중" → "완료" 상태 변화를 확인
   (폴링 또는 dcat_provenance/data_registry 조회 API 필요 — §7)
```

### 4.3 "즉시 수집"이 필요하면

15분 틱을 기다리기 싫다면(사용자가 등록 직후 결과를 바로 보고 싶어함), 백엔드 API가
3번 단계 직후 Airflow REST API로 즉시 DagRun을 트리거할 수 있다:

```python
# 백엔드 API, dcat_dataset/data_registry INSERT 직후
POST {AIRFLOW_URL}/api/v1/dags/collect_video/dagRuns
{"conf": {"dataset_id": "user_abc123"}}
```

이 경우 DAG를 살짝 손봐야 한다 — `conf`로 특정 dataset_id가 넘어오면 그 하나만,
없으면(정기 틱) `get_due_dataset_ids()`로 전체를 도는 분기가 필요하다. 초기 버전은
"15분 이내 자동 반영"으로 충분하다면 이 트리거 API 연동은 나중으로 미뤄도 된다 —
**MVP 범위 결정 필요** (§8).

### 4.4 채널명 검증: 사용자 입력 vs API 조회값

사용자가 입력한 "채널명"과 YouTube API가 실제로 반환하는 채널명이 다를 수 있다
(오타, 채널명 변경 등). 권장: `dcat_dataset.title`은 **사용자가 입력한 데이터셋
제목**(사람이 관리 목적으로 붙이는 이름, 예: "우리 회사 경쟁사 채널 모음")으로 쓰고,
API가 반환하는 실제 채널명은 `meta_youtube_video.channel_title`에 수집 시점마다
채워지는 것으로 이미 스키마가 분리되어 있다 — 별도 조치 불필요, 다만 프론트엔드
쪽에서 이 둘이 다른 개념이라는 걸 헷갈리지 않게 UI 문구로 구분해야 한다.

### 4.5 "동일 source_type, 기존 데이터셋에 채널만 추가"하는 경우

새 `dcat_dataset` 행을 만드는 대신, **기존 사용자 데이터셋의 `subjects` 배열에 채널
ID를 추가**하는 경우도 있다 (`dataset_origin='user'`는 원래 "동일 소스 타입 내 복수
채널 자유 조합"을 위해 설계됨 — `datagokr_schema.md` 참조). 이 경우:

- `dcat_dataset.subjects` UPDATE만 하면 된다 (`item_count`/`updated_at`도 같이 갱신)
- `data_registry`/Airflow 쪽은 **아무것도 건드릴 필요 없음** — 같은 dataset_id의 다음
  수집 실행 때 Collector가 `subjects`를 다시 읽어서 새 채널도 자동으로 포함
- 즉 "새 dcat_dataset 생성" 경로보다 훨씬 가볍다. 프론트엔드에서 "새 컬렉션 만들기"
  와 "기존 컬렉션에 채널 추가"를 구분된 UX로 제공하는 걸 권장

---

## 5. 실패 처리 · 재시도 · 모니터링

- **Collector 레벨**: 실패 시 `dcat_provenance.status='failure'` + `error_message` 기록,
  `data_registry.status='error'` + `last_error` 기록, `next_collect_at`은 **당김**(예: 1시간
  후 재시도) — 다음 정기 주기까지 기다리지 않도록.
- **Airflow 레벨**: task 자체의 재시도(`retries=3`, `retry_delay`)는 네트워크 순간 오류
  등 코드 레벨 예외에 대한 것이고, 위 DB 기반 `status='error'` 처리와는 별개 레이어.
  Collector의 `run()`이 예외를 삼키지 않고 그대로 올려야 Airflow 재시도가 의미 있다.
- **모니터링**: `data_registry WHERE status='error'` 조회가 사실상의 알림 대시보드
  쿼리. 초기엔 수동 조회, 이후 Slack 알림 등은 별도 과제(ADR-002의 "실패 모니터링
  고도화" 조건과 직결).

---

## 6. API Key 저장 모델 — 결정: 데이터셋별 저장 (옵션 B)

`05_Secrets_ConfigMaps.md`의 기존 모델은 플랫폼 전체가 K8s Secret 하나(`youtube-api-secret`,
`naver-api-secret`)를 공유하는 구조였다. 사용자가 데이터셋 등록 시 자신의 API Key를
직접 입력하는 것으로 확정했다 — K8s Secret은 사용자 수만큼 동적으로 늘리기엔 부적합해서
(K8s API 호출 필요, Secret 목록 관리 부담) 새 테이블 `sql/dataset_credentials.sql`을
만들어 DB에 암호화 저장하는 방식을 택했다. 이 프로젝트가 기존에도 별도 인프라를
새로 세우기보다 PostgreSQL로 해결해온 기조(ADR-003 pgvector, ADR-004 SeaweedFS 선정
이유 참조)와 일치한다.

### 6.1 저장 방식

- **암호화**: PostgreSQL `pgcrypto` 확장의 `pgp_sym_encrypt`/`pgp_sym_decrypt` (대칭키)
- **대칭키 위치**: DB가 아니라 K8s Secret(`dataset-credentials-encryption-key`)에 별도 보관
  — DB 접근 권한만으로는 평문을 복호화할 수 없도록 계층을 분리
- **테이블 분리 이유**: `dcat_dataset`은 일반 조회·조인이 잦은 테이블이라, 민감정보를
  거기 컬럼으로 두면 API 응답에 실수로 섞여 나갈 위험이 있다. `dataset_credentials`를
  물리적으로 분리하고 이 테이블에 대한 DB 권한을 Collector 실행 계정으로만 좁힌다.
- **Fallback**: `dataset_credentials`에 해당 dataset_id 행이 없으면 Collector는 플랫폼
  공유 키(`youtube-api-secret` 등)로 폴백한다 — 사용자가 키를 안 넣어도 데이터셋 등록
  자체는 가능. (프론트엔드에서 입력을 필수로 강제할지는 별도 UX 결정 사항으로 남김)

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

## 7. 프론트엔드-백엔드 API 계약 (초안, `docs/api/`로 승격 필요)

지금 `docs/api/Metadata_API.md`, `Catalog_API.md`는 둘 다 미작성 상태다. 이 문서에서
필요하다고 확인된 엔드포인트만 초벌로 적어둔다 — 실제 스펙 문서화는 별도 작업.

```
POST   /api/datasets              신규 데이터셋 등록 (§4.2)
PATCH  /api/datasets/{id}/subjects   기존 데이터셋에 채널/키워드 추가 (§4.5)
GET    /api/datasets/{id}/status  수집 상태 조회 (data_registry.status, last_collected_at 등)
POST   /api/datasets/{id}/collect-now   즉시 수집 트리거 (§4.3, MVP 이후)
```

---

## 8. 이 설계를 실행하기 전에 확정해야 할 것 (요약)

- [ ] **ADR-002 갱신 여부** — 이 문서의 §서두 판단(사실상 Airflow 도입 조건 충족)에
      동의하는지, 동의하면 ADR-002를 Superseded 처리하고 새 ADR(예: ADR-006 또는
      다음 번호)로 "Airflow 도입 확정"을 기록할지
- [x] ~~API Key 모델~~ — §6 결정 완료 (데이터셋별 저장, `dataset_credentials` 테이블 + pgcrypto)
- [ ] **즉시 수집 트리거 필요 여부** — §4.3, MVP 범위에 넣을지 15분 지연을 감수할지
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
