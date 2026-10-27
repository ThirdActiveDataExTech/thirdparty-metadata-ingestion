# ADR 008: 경량 자체 스케줄러 채택 (ADR-007 Superseded)

> **Date:** 2026-10-27
> **Status:** Accepted
> **Supersedes:** [ADR-007](007_Airflow_Adoption.md)

---

## 배경

[ADR-007](007_Airflow_Adoption.md)은 Airflow 도입을 확정했다. 근거는 다음과 같았다.

> 데이터셋마다 정적 K8s CronJob YAML을 작성하고 재배포해야 하는 구조는,
> "등록하면 자동으로 수집 스케줄이 생겨야 한다"는 요구사항과 구조적으로 맞지 않는다.

2026-10-27 연구개발계획서 기반 전수 검증 과정에서 **이 전제가 잘못된 이분법**임이 확인되었다.

- "데이터셋마다 CronJob 1개"는 선택지 중 하나일 뿐이다.
- 실제 선택지는 **"CronJob 1개가 주기적으로 깨어나 `data_registry.next_collect_at`이 지난
  데이터셋을 집어 실행"** 이며, 이 방식은 동적 등록 요구사항을 그대로 충족하고 재배포도 필요 없다.
- ADR-007은 이 선택지를 검토하지 않았다.

### 필요한 재료가 이미 모두 존재한다

| 재료 | 현 상태 |
|---|---|
| `data_registry.next_collect_at` | 매 실행마다 `accrual_periodicity` 기반으로 갱신 중 |
| `idx_data_registry_next` | 인덱스 생성 완료 (`sql/data_registry.sql`) |
| `run_dataset(dataset_id)` | `src/main.py`에 구현 완료 — 오케스트레이터 무관 계약 |
| `dcat_provenance` | 실행 이력(started_at/ended_at/status/rows_affected/error_message) 적재 중 |
| PgBouncer | **미사용 확인** → 세션 어드바이저리 락 사용 가능 |

→ 스케줄러 구현량은 **실질 30줄**이다.

### Airflow 동적 DAG의 역효과

DB에서 데이터셋 목록을 읽어 DAG를 생성하면, DAG 파일은 `min_file_process_interval`
(기본 30초)마다 재파싱되고 **그때마다 해당 DB 조회가 실행된다.** Airflow 공식 FAQ도
"생성 코드가 외부 시스템에 연결하면 성능 문제가 생길 수 있다"고 명시한다.

이를 피하려 간격을 600초로 올리면 **신규 데이터셋이 최대 10분 뒤에야 DAG로 뜬다.**
ADR-007이 원했던 "등록 즉시 반영"과 오히려 멀어진다.

## 결정

**Airflow를 도입하지 않는다.** 대신 다음을 채택한다.

1. **K8s CronJob 1개**를 `*/15 * * * *`로 두고, `next_collect_at <= now()`인 데이터셋을
   `LIMIT`만큼 집어 `run_dataset()`을 호출한다.
   주기 15분은 와이즈넛 별첨 테이블정의서의 `data_registry.next_collect_at` 규약
   ("스케줄러 폴링 조건 · 15분 주기")에 맞춘 값이다. 최소 수집주기가 일 단위이므로
   폴링 지터는 문제가 되지 않는다.
2. 중복 실행은 **`pg_try_advisory_lock(네임스페이스, hash(dataset_id))` 2-키 형태**로 막는다.
   세션 락이므로 커넥션이 끊기면 자동 해제되어 TTL·하트비트가 불필요하다.
   CronJob `concurrencyPolicy: Forbid`를 함께 건다.
3. 파이프라인은 **선언형 YAML 명세를 해석하는 자체 경량 러너**로 실행한다(구현량 150~250줄).
4. 락 획득 실패는 **에러가 아니다.** debug 로그 후 skip하면 다음 틱에 자연히 재시도된다.

## 받아들이는 대가

**자체 러너에는 UI가 없다.** 실행 상태를 보려면 SQL을 쳐야 한다.
이를 보완하기 위해 `dcat_provenance` 조회 뷰 + 조회 CLI(또는 Grafana PostgreSQL 패널)를
최소한으로 제공한다. 이 비용을 "Airflow 미도입의 대가"로 명시적으로 계상한다.

또한 스케줄러 CronJob은 단일 장애점이다. 다만 실패해도 다음 틱(5분 뒤)에 복구되고
`next_collect_at`이 유지되므로 **데이터 손실은 없다.** 수용 가능한 리스크로 판단한다.

## ADR-007의 설계 원칙은 그대로 유효하다

- Collector는 `run(dataset_id)`를 노출하고, 자신이 무엇에 의해 실행되는지 모른다 — 그대로 유지
- 따라서 **향후 전환 비용이 낮다.** 데이터셋 간 의존관계나 백필 요구가 실제로 발생하면
  그때 외부 오케스트레이터로 이행한다.

## 전환 재검토 조건

- 데이터셋 간 **의존관계**가 생길 때
- **백필·재처리**를 단계 단위로 해야 할 때
- 분산 팬아웃이 필요한 규모가 될 때

## 참고

- 상세 설계·함정: [development/04_Implementation_Methods.md](../development/04_Implementation_Methods.md) §3 C4, §4.4
