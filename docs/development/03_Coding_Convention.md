# 03. Coding Convention

> **Last Updated:** 2026-07-28
> §6.1 실 구현 과정에서 아키텍처가 `Collector → Preprocess → Extractor → Storage`
> 단방향 레이어 구상에서 `collectors/`+`pipelines/`+`database/`+`storage/` 구조로
> 확정됐다(별도 Preprocess/Extractor 레이어 없음) — 아래 원칙을 그에 맞게 갱신.
> 상세: [architecture/03_Component_Architecture.md](../architecture/03_Component_Architecture.md)

---

## 기본 원칙

- `print()`는 라이브러리 코드(`src/`)에선 지양하고 `logging` 사용, `scripts/`의
  CLI 출력(사용자에게 진행상황 보여주는 용도)은 `print()` 허용
- 코드 내부에 비밀번호, API Key 하드코딩 금지 — 환경변수 사용
- `collectors/`(순수 외부 API 호출) → `pipelines/`(collectors+database 조합,
  `run()` 노출) → `database/`(순수 DB IO) — `storage/`(SeaweedFS 저장)는
  `pipelines/`가 호출하는 방향만 지키면 됨. 상세 규칙:
  [architecture/03_Component_Architecture.md](../architecture/03_Component_Architecture.md) "모듈 간 의존 규칙"
- `collectors/`는 DB에 직접 접근하지 않는다

## 파일 명명

```
collectors/naver_shopping_collector.py   # {소스명}_collector.py
collectors/youtube_collector.py
pipelines/naver_shopping_pipeline.py     # {소스명}_pipeline.py — run(dataset_id, triggered_by) 노출
database/meta_naver_shopping.py          # meta_{소스명}.py
```

## 함수 단위

- 각 모듈은 `run()` 또는 명확한 진입 함수를 노출한다
- `if __name__ == '__main__':` 블록에만 실행 로직을 두지 않는다
  - Airflow Task에서 import해서 호출할 수 있어야 하기 때문

## triggered_by 주입 방식

```python
# src/common/config.py — 지금은 .env의 TRIGGERED_BY(기본값 'manual')로 주입,
# main.py의 run_dataset()이 명시적으로 안 주면 이 기본값을 씀
TRIGGERED_BY = get_env("TRIGGERED_BY", "manual")
```

K8s CronJob/Airflow는 아직 없음(§6.2 미착수) — 그때 가면 아래처럼 실행 주체별로
다른 값을 주입할 것:
```yaml
env:
  - name: TRIGGERED_BY
    value: "Airflow collect_video/{dataset_id}"
```
