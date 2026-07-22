# Metadata Ingestion — Documentation

> **Last Updated:** 2026-07-22
> **Project:** metadata-ingestion
> **Purpose:** 다양한 공공데이터 및 외부 API를 수집하여 메타데이터를 정제·저장하는 플랫폼

---

> 🚧 **지금 뭘 해야 하는지 모르겠다면** → [NEXT_STEPS.md](NEXT_STEPS.md) 먼저 확인.
> 남은 작업이 순서대로 정리되어 있다.

---

## 1. Infrastructure

현재 서버 구성과 Kubernetes, 스토리지, 인증 정보 관리에 관한 문서.
**서버 상태나 연결 정보가 바뀔 때 업데이트한다.**

| # | 문서 | 설명 | 상태 |
|---|------|------|------|
| 1.1 | [Current Infrastructure](infrastructure/01_Current_Infrastructure.md) | 현재 서버에 무엇이 있는가 | 완성 |
| 1.2 | [Kubernetes](infrastructure/02_Kubernetes.md) | 클러스터 구조, 배포 방식 | 완성 |
| 1.3 | [PostgreSQL](infrastructure/03_PostgreSQL.md) | DB 두 개 연결 정보 및 스키마 | 완성 |
| 1.4 | [Object Storage (SeaweedFS)](infrastructure/04_ObjectStorage.md) | 오브젝트 스토리지 구조 (MinIO → SeaweedFS 전환) | 완성 (배포·연결 완료) |
| 1.5 | [Secrets & ConfigMaps](infrastructure/05_Secrets_ConfigMaps.md) | 환경변수 및 인증 정보 관리 | 완성 |
| 1.6 | [Vector DB](infrastructure/06_VectorDB.md) | pgvector 구성 및 Qdrant 전환 전략 | 완성 (임베딩 파이프라인 운영 중) |

---

## 2. Architecture

시스템 전체 구조와 데이터 흐름에 관한 문서.
**개발이 진행되면서 채워진다.**

| # | 문서 | 설명 | 상태 |
|---|------|------|------|
| 2.1 | [System Architecture](architecture/01_System_Architecture.md) | 전체 시스템 구조 | 작성 중 |
| 2.2 | [Metadata Flow](architecture/02_Metadata_Flow.md) | 수집 → 전처리 → 저장 흐름 | 작성 중 |
| 2.3 | [Component Architecture](architecture/03_Component_Architecture.md) | 컴포넌트 역할 및 관계 | 작성 중 |
| 2.4 | [Collection Pipeline Operations](architecture/04_Collection_Pipeline_Operations.md) | Airflow 기반 동적 수집 스케줄링, 신규 데이터셋 온보딩 흐름 | 설계안 (구현 전) |

---

## 3. Development Guide

로컬 개발환경 구성, 배포 절차, 코딩 컨벤션에 관한 문서.

| # | 문서 | 설명 | 상태 |
|---|------|------|------|
| 3.1 | [Local Development](development/01_Local_Development.md) | 로컬 환경 구성 | 작성 중 |
| 3.2 | [Deployment](development/02_Deployment.md) | Git → Docker → Kubernetes 배포 | 작성 중 |
| 3.3 | [Coding Convention](development/03_Coding_Convention.md) | 코드 작성 규칙 | 완성 |

---

## 4. Data Sources

데이터 소스별 API 스펙, 수집 로직, 주의사항.
**새 데이터 소스 추가 시 반드시 문서를 먼저 작성한다.**

| 문서 | dataset_id | source_type | 상태 |
|------|-----------|-------------|------|
| [Naver Shopping Insight](data-sources/naver_shopping_insight.md) | `naver_shopping_insight` | shopping | 완성 |
| [Naver Persona Insight](data-sources/naver_persona_insight.md) | `naver_persona_insight` | shopping | 완성 |
| [YouTube](data-sources/youtube.md) | `youtube_{채널명}` | video | 작성 중 |
| [Naver News](data-sources/naver_news.md) | `naver_news_{주제}` | news | 작성 중 |

---

## 5. Runbooks

운영 절차서. 자주 쓰는 작업은 여기서 찾는다.

| 문서 | 설명 |
|------|------|
| [새 데이터 소스 추가](runbooks/01_Add_New_DataSource.md) | 체크리스트 |
| [수집 실패 대응](runbooks/02_Troubleshoot_Failed_Collection.md) | 원인별 대응 방법 |
| [수동 수집 실행](runbooks/03_Manual_Collection.md) | 로컬/K8s 수동 실행 |
| [기존 source_type 내 새 데이터셋 추가](runbooks/04_Add_New_Dataset_Existing_Source.md) | 신규 플랫폼 추가보다 가벼운 케이스 (채널/검색어만 추가) |

---

## 6. Database

DB 스키마, 테이블 정의. **테이블이 추가되거나 컬럼이 변경될 때 업데이트한다.**

| 문서 | 설명 | 상태 |
|------|------|------|
| [datagokr Schema](database/datagokr_schema.md) | metadata-ingestion 메인 DB | 완성 (테이블 대부분 생성 완료) |
| [thirdparty Schema](database/thirdparty_schema.md) | 기존 thirdparty DB | 미작성 |

---

## 7. API

수집된 메타데이터를 조회·활용하는 API 문서. **API 개발 시 작성한다.**

| 문서 | 설명 | 상태 |
|------|------|------|
| [Metadata API](api/Metadata_API.md) | 메타데이터 조회 API | 미작성 |
| [Catalog API](api/Catalog_API.md) | 카탈로그 API | 미작성 |

---

## 8. Architecture Decision Records (ADR)

설계 결정의 배경과 이유를 기록한다. **한번 결정되면 수정하지 않고 새 ADR로 override한다.**

| # | 문서 | 상태 |
|---|------|------|
| ADR-001 | [DCAT을 메타데이터 표준으로 채택](adr/001_DCAT_as_metadata_standard.md) | Accepted |
| ADR-002 | [Airflow 도입 전 K8s CronJob 사용](adr/002_KubernetesCronJob_before_Airflow.md) | Accepted |
| ADR-003 | [Vector DB 전략 — pgvector 시작, Qdrant 전환 경로](adr/003_VectorDB_Strategy.md) | Accepted |
| ADR-004 | [Object Storage 전략 — MinIO → SeaweedFS 전환](adr/004_ObjectStorage_Strategy.md) | Accepted |
| ADR-005 | [Naver 뉴스 수집 가능 지표 결정](adr/005_Naver_News_Metrics_Decision.md) | Accepted |

---

## 9. Research

이 플랫폼의 데이터·인프라를 활용한 논문 주제 기획 및 초안. 프로젝트 개발 문서와는
별도 트랙이며, 인프라/스키마가 바뀌어도 자동 동기화되지 않으니 참고 시 주의.

| 문서 | 설명 |
|------|------|
| [연구 주제 후보 요약](research/paper_topics.md) | 주제 7개 개요 + 우선순위 |
| [연구 기획서 모음](research/research_proposals.md) | P01–P07 상세 기획서 (연구질문·방법·평가·해석기준) |

각 주제(P01–P07)마다 논문 형식 초안이 2개씩 있다 (`research/` 폴더, `paper_draft_P0X_*.md` /
`paper_P0X_*_mock_draft.md`): `[DATA: ...]` 자리만 채우면 되는 템플릿과, 그 자리를 가상
수치로 채운 예시본. 가상 수치본은 파일 상단에 경고 배너가 있다.
