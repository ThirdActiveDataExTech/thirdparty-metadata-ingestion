# metadata-ingestion

써드파티 데이터(공공데이터·외부 API)를 수집하여 **메타데이터를 정제·표준화·저장**하고, 의미 기반 검색까지 연결하는 **액티브 메타데이터 기반 데이터 확장 플랫폼**의 수집·저장 파이프라인.

> 국책과제 RS-2024-00340834 「써드파티 데이터의 활용성 증대를 위한 액티브 메타데이터 기반 능동형 데이터 확장 기술 개발」 (주관 ㈜모비젠)

## 개요

- **수집 소스(5종)**: YouTube · 네이버 뉴스 · 네이버 블로그 · 쇼핑인사이트 · 페르소나
- **메타데이터 저장**: PostgreSQL 17 + pgvector (DCAT 표준 구조, 소스별 `meta_*` / 시계열 `active_meta_*`)
- **원본·배포본 저장**: SeaweedFS(S3 호환) — 원본(`raw/`) + JSON-LD 배포본(`jsonld/`)
- **의미 검색**: 임베딩(pgvector, 768차원) 기반 2단계(데이터셋·아이템) 벡터 검색

## 디렉토리 구조

| 경로 | 설명 |
|---|---|
| `src/` | 수집·저장 파이프라인 (`collectors/`·`pipelines/`·`database/`·`storage/`·`common/`) |
| `sql/` | 테이블/뷰 DDL, 시드 |
| `scripts/` | 데이터셋 등록·임베딩·검색·백필 등 운영 스크립트 |
| `k8s/` | 쿠버네티스 매니페스트 (secrets는 `*.template`만 추적) |
| `tests/` | 테스트 |
| `docs/` | 설계·운영·스키마 문서 (진입점: [docs/00_Index.md](docs/00_Index.md)) |

## 문서

- **문서 인덱스**: [docs/00_Index.md](docs/00_Index.md)
- **작업 로드맵(단일 소스)**: [docs/NEXT_STEPS.md](docs/NEXT_STEPS.md)
- **DB 스키마**: [docs/database/datagokr_schema.md](docs/database/datagokr_schema.md)
- **저장 형식 명세(원본·JSON-LD)**: [docs/architecture/06_Object_Storage_Format_Spec.md](docs/architecture/06_Object_Storage_Format_Spec.md)

## 설정

접속 정보·자격증명은 **환경변수(`.env`)와 K8s Secret**으로만 주입한다(코드·문서에 평문 금지). 예시는 [.env.example](.env.example) 참조.
