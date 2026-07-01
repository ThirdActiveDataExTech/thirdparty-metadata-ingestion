# 03. Coding Convention

> **Last Updated:** 2026-07-01

---

## 기본 원칙

- `print()` 사용 금지 — `logging` 모듈 사용
- 코드 내부에 비밀번호, API Key 하드코딩 금지 — 환경변수 사용
- `Collector` → `Preprocess` → `Extractor` → `Storage` 단방향 의존
- `Collector`는 DB에 직접 접근하지 않는다

## 파일 명명

```
collectors/naver_shopping_insight.py   # 소스명_기능.py
collectors/youtube_collector.py
```

## 함수 단위

- 각 모듈은 `run()` 또는 명확한 진입 함수를 노출한다
- `if __name__ == '__main__':` 블록에만 실행 로직을 두지 않는다
  - Airflow Task에서 import해서 호출할 수 있어야 하기 때문

## triggered_by 주입 방식

```python
import os
triggered_by = os.getenv('TRIGGERED_BY', 'manual')
```

K8s CronJob YAML에서 주입:
```yaml
env:
  - name: TRIGGERED_BY
    value: "K8s CronJob naver-shopping-cronjob"
```
