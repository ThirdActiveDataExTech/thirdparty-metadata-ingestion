# 03. Component Architecture

> **Last Updated:** 2026-07-27
> **Status:** 구현 진행 중 (§6.1 YouTube/Naver Shopping 파일럿 완료, NEXT_STEPS.md 참조)

---

## src/ 구조 (실제 구현 기준)

```
src/
├── common/
│   ├── config.py      .env 로딩, DB 접속 정보 등 공통 상수
│   └── retry.py        간단한 재시도+백오프 헬퍼 (일시적 오류만 재시도)
├── database/           DB IO — collectors/에서 분리된 이유는 아래 참조
│   ├── db.py            get_conn() — psycopg2 연결
│   ├── dcat.py           dcat_dataset/dcat_provenance/data_registry/dataset_credentials
│   │                     공통 헬퍼 (모든 source_type이 공유)
│   └── meta_{source}.py  소스별 meta_*/active_meta_* 읽기·쓰기 (예: meta_youtube.py)
├── collectors/          외부 API 호출, Raw Data 반환 — DB 직접 접근 금지
│   └── {source}_collector.py, naver_datalab_scale.py(순수 보정 수학) 등
├── pipelines/
│   └── {source}_pipeline.py   run(dataset_id, triggered_by) — Airflow/CLI가 부르는 진입점
└── main.py               CLI: `python -m src.main run <dataset_id>` (수동 실행/검증용)
```

`preprocess/`·`extractor/`는 별도 빈 레이어로 두지 않았다 — 실제로 필요한 변환(원시 API
JSON → DB 컬럼)이 소규모라 `collectors`/`pipelines` 내부 헬퍼 함수로 충분하다고 판단
(2026-07-27, §6.1 파일럿 구현 중 결정).

## 모듈 간 의존 규칙

- `collectors/`는 순수 외부 API 호출만 한다 — **DB에 직접 접근하지 않는다.**
- `database/`는 순수 DB IO만 한다 — 외부 API를 호출하지 않는다.
- **`pipelines/`가 이 둘을 조합한다.** `run(dataset_id, triggered_by)` 함수가
  `collectors`로 fetch → 신규/기존 diff → `database`로 저장 → `dcat_provenance`/
  `data_registry` 갱신까지 전부 수행한다. Airflow(§6.2)나 `main.py`는 `pipelines/`만
  참조하면 된다 — ADR-002/007이 정의한 "오케스트레이터 무관 `run(dataset_id)`" 계약이
  이 레이어에 있다.
- `main.py`가 CLI 진입점(수동 실행)을 조립하는 지점 — `dataset_id`의 `source_type`을
  보고 알맞은 `pipelines/{source}_pipeline.py`로 위임한다.

> 이전 버전 문서는 "collector가 `run()`도 노출한다"는 취지로 읽힐 수 있었는데, 실제
> 구현 단계에서 그렇게 하면 `collector`가 DB에도 접근하게 돼 위 "DB 직접 접근 금지"
> 규칙과 모순됐다. `pipelines/` 레이어를 신설해 collector는 여전히 순수하게 유지하고,
> `run()`은 pipelines가 노출하는 것으로 정리했다.

---

*Airflow 도입 시 `pipelines/{source}_pipeline.run()`이 Task 단위로 매핑된다. 모듈
구조는 변경하지 않는다.*
