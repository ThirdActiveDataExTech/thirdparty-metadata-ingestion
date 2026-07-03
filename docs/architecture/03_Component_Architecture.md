# 03. Component Architecture

> **Last Updated:** 2026-07-01
> **Status:** 작성 중

---

## src/ 구조

```
src/
├── collectors/     외부 API 호출, Raw Data 반환 (DB 직접 접근 금지)
├── preprocess/     Raw Data 정제 및 정규화
├── extractor/      메타데이터 추출 (DCAT, Schema.org)
├── storage/        SeaweedFS (S3 API) / PostgreSQL 저장
├── database/       DB 연결, 쿼리 유틸
├── common/         공통 유틸 (로깅, 설정, 예외)
└── main.py         파이프라인 진입점
```

## 모듈 간 의존 규칙

- `collector` → `preprocess` → `extractor` → `storage` 단방향
- `collector`는 DB에 직접 접근하지 않는다
- `main.py`가 전체를 조립하는 유일한 지점

---

*Airflow 도입 시 각 모듈이 Task 단위로 분리된다. 모듈 구조는 변경하지 않는다.*
