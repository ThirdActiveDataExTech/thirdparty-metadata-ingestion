# 01. Local Development

> **Last Updated:** 2026-07-01
> **Status:** 작성 중 — src/ 코드 구조 확정 후 업데이트

---

## 개발 환경

| 항목 | 값 |
|------|-----|
| OS | macOS |
| Python | 3.11+ |
| DB 접속 | 서버 PostgreSQL NodePort 직접 접속 (localhost:30433) |
| IDE | VSCode + Claude Code |

---

## 초기 설정

```bash
# 1. 저장소 클론
git clone <repo-url>
cd metadata-ingestion

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 환경변수 설정
cp .env.example .env
# .env 파일에 실제 값 입력 (05_Secrets_ConfigMaps.md 참고)

# 4. DB 연결 확인
python -c "import psycopg2; conn = psycopg2.connect(...); print('OK')"
```

---

## 실행

```bash
# 전체 파이프라인 실행
python src/main.py

# 특정 소스만 실행 (예정)
python src/main.py --source naver_shopping
```

---

*상세 내용은 src/ 코드 구조 확정 후 작성.*
