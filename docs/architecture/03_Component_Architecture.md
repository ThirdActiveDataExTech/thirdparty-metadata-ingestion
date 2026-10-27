# 03. Component Architecture

> **Last Updated:** 2026-07-28
> **Status:** §6.1(5개 소스 Collector) + SeaweedFS raw/JSON-LD export 구현·검증 완료
> (NEXT_STEPS.md 참조)

---

## src/ 구조 (실제 구현 기준)

```
src/
├── common/
│   ├── config.py      .env 로딩, DB/S3 접속 정보 등 공통 상수
│   └── retry.py        간단한 재시도+백오프 헬퍼 (일시적 오류만 재시도)
├── database/           DB IO — collectors/에서 분리된 이유는 아래 참조
│   ├── db.py            get_conn() — psycopg2 연결, 프로세스당 1개 재사용(2026-07-28
│   │                     성능 개선, 멀티스레드 비세이프 — 파일 상단 docstring 참조)
│   ├── dcat.py           dcat_dataset/dcat_provenance/data_registry/dataset_credentials
│   │                     공통 헬퍼 (모든 source_type이 공유)
│   └── meta_{source}.py  소스별 meta_*/active_meta_* 읽기·쓰기 (예: meta_video.py)
├── collectors/          외부 API 호출, Raw Data 반환 — DB 직접 접근 금지
│   ├── {source}_collector.py, naver_datalab_scale.py(순수 보정 수학) 등
│   └── youtube_transcript_collector.py  yt-dlp 오디오 다운로드 + faster-whisper
│                         로컬 STT(자체) — 레거시의 비공식 API 직접 호출은 IP 차단
│                         확인돼 미채택, architecture/05_Object_Storage_Export.md §4
├── pipelines/
│   └── {source}_pipeline.py   run(dataset_id, triggered_by) — Airflow/CLI가 부르는 진입점
├── storage/              SeaweedFS(S3) raw/JSON-LD 저장 (2026-07-28 신설)
│   ├── s3_client.py       boto3 클라이언트, 업로드 헬퍼
│   ├── raw_export.py      아이템 단위 raw 파일 쓰기(트랜스크립트/본문/CSV)
│   └── jsonld_export.py   source_type별 JSON-LD 생성 — dcat_dataset+아이템+
│                           active metadata 통합, 데이터셋당 1개
└── main.py               CLI: `python -m src.main run <dataset_id>` (수동 실행/검증용)
```

`preprocess/`·`extractor/`는 별도 빈 레이어로 두지 않았다 — 실제로 필요한 변환(원시 API
JSON → DB 컬럼)이 소규모라 `collectors`/`pipelines` 내부 헬퍼 함수로 충분하다고 판단
(2026-07-27, §6.1 파일럿 구현 중 결정). SeaweedFS 저장은 위와 같은 이유로 `storage/`
레이어를 별도로 뒀다 — collectors/pipelines와 성격이 달라(외부 API 호출도, DB IO도
아닌 "DB에서 읽어 S3에 쓰는" 별개 관심사) 기존 두 레이어 어디에도 억지로 끼워넣지
않는 게 자연스럽다고 판단.

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
- `storage/`는 `database/`(DB에서 현재 상태 조회)와 S3 업로드를 동시에 다룬다 —
  위 "순수 DB IO만"/"순수 API 호출만" 규칙의 예외인데, `pipelines/`가 `storage/`를
  호출하는 방향(반대 방향 없음)만 지키면 된다. `pipelines/*.py`의 `run()`이
  DB 커밋 성공 직후 `storage.jsonld_export.export_dataset(dataset_id)`를 호출하는
  구조(§5, `05_Object_Storage_Export.md`).

> 이전 버전 문서는 "collector가 `run()`도 노출한다"는 취지로 읽힐 수 있었는데, 실제
> 구현 단계에서 그렇게 하면 `collector`가 DB에도 접근하게 돼 위 "DB 직접 접근 금지"
> 규칙과 모순됐다. `pipelines/` 레이어를 신설해 collector는 여전히 순수하게 유지하고,
> `run()`은 pipelines가 노출하는 것으로 정리했다.

---

*Airflow 도입 시 `pipelines/{source}_pipeline.run()`이 Task 단위로 매핑된다. 모듈
구조는 변경하지 않는다.*
