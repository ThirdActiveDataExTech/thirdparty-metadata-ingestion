# ADR 002: Airflow 도입 전 K8s CronJob으로 수집 스케줄링

> **Date:** 2026-07-01
> **Status:** Superseded by [ADR-007](007_Airflow_Adoption.md) (2026-07-23)
>
> 프론트엔드발 동적 데이터셋 등록 설계([architecture/04_Collection_Pipeline_Operations.md](../architecture/04_Collection_Pipeline_Operations.md)
> 서두)에서 이 ADR의 "단계별 재실행 필요" 조건이 사실상 충족됐다고 판단, Airflow 도입을
> 확정했다. 아래 내용은 과거 결정 기록으로 보존한다 — 현재 유효한 결정은 ADR-007 참조.

---

## 배경

수집 스크립트의 주기적 실행이 필요하다. Airflow vs K8s CronJob 중 선택이 필요했다.

## 결정

현재는 K8s CronJob을 사용한다. Airflow는 조건 충족 시 도입한다.

## Airflow 도입 조건 (하나라도 충족 시)

- 데이터 소스 10개 이상
- 단계별 재실행 필요
- 실패 모니터링 고도화 필요

## 수집 코드 설계 원칙

Airflow 도입 시 코드 변경 없이 전환 가능하도록 설계한다.

- 각 Collector는 `run()` 함수를 노출 (import해서 호출 가능)
- `triggered_by`는 환경변수 `TRIGGERED_BY`로 주입 (오케스트레이터 무관)
- K8s CronJob → Airflow Task로 전환 시 수집 코드는 변경하지 않는다
