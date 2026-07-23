# ADR 007: Airflow 도입 확정 (ADR-002 Superseded)

> **Date:** 2026-07-23
> **Status:** Accepted
> **Supersedes:** [ADR-002](002_KubernetesCronJob_before_Airflow.md)

---

## 배경

[ADR-002](002_KubernetesCronJob_before_Airflow.md)는 K8s CronJob을 기본으로 하고, 아래
조건 중 하나라도 충족하면 Airflow를 도입하기로 했다.

- 데이터 소스 10개 이상
- 단계별 재실행 필요
- 실패 모니터링 고도화 필요

이후 플랫폼 프론트엔드에서 사용자가 직접 새 데이터셋(YouTube 채널, 검색어, 카테고리 등)을
동적으로 등록하는 설계를 진행하면서([architecture/04_Collection_Pipeline_Operations.md](../architecture/04_Collection_Pipeline_Operations.md))
다음 문제가 드러났다.

- 데이터셋마다 정적 K8s CronJob YAML을 작성하고 재배포해야 하는 구조는, "등록하면 자동으로
  수집 스케줄이 생겨야 한다"는 요구사항과 구조적으로 맞지 않는다.
- 이는 ADR-002의 "단계별 재실행 필요" 조건과 사실상 같은 문제로, Airflow의 Dynamic Task
  Mapping이 정확히 해결하는 문제다.

## 결정

**Airflow 도입을 확정한다.** `data_registry` 테이블을 스케줄의 단일 진실 공급원(SSOT)으로
삼고, source_type당 DAG 1개 + Dynamic Task Mapping으로 동적 데이터셋을 처리한다. 상세
설계는 [architecture/04_Collection_Pipeline_Operations.md](../architecture/04_Collection_Pipeline_Operations.md)
§3(DAG 설계) 참조.

## ADR-002의 설계 원칙은 그대로 유효하다

ADR-002가 미리 요구했던 "Airflow 도입 시 코드 변경 없이 전환 가능한 설계"가 실제로
그대로 들어맞는다 — 별도 마이그레이션 작업이 필요 없다.

- 각 Collector는 `run(dataset_id)` 함수를 노출한다 (import해서 호출 가능) — 그대로 유지
- Collector 코드는 자신이 Airflow에 의해 실행되는지 K8s CronJob에 의해 실행되는지 모른다
- `dags/`에 Airflow Task가 이 `run()`을 호출하기만 하면 된다

## 남은 작업

이 ADR은 방향 결정이고, 실제 Airflow 배포 방법(K8s에 Helm chart로 설치할지 등)은 별도
인프라 문서로 다룬다(`docs/infrastructure/07_Airflow.md` 후보, 아직 미작성). 진행 상황은
`docs/NEXT_STEPS.md` §6.2 참조.
