"""환경변수 로딩 — scripts/embed_*.py의 load_dotenv 패턴을 공유 모듈로 옮긴 것."""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"필수 환경변수 {name}가 설정되지 않았습니다 (.env 확인)")
    return value


DB_HOST = get_env("DB_HOST", "localhost")
DB_PORT = int(get_env("DB_PORT", "30433"))
DB_NAME = get_env("DB_NAME", "datagokr")
DB_USER = get_env("DB_USER")
DB_PASSWORD = get_env("DB_PASSWORD")

TRIGGERED_BY = get_env("TRIGGERED_BY", "manual")

S3_ENDPOINT = get_env("S3_ENDPOINT", "http://localhost:30920")
S3_ACCESS_KEY = get_env("S3_ACCESS_KEY")
S3_SECRET_KEY = get_env("S3_SECRET_KEY")
S3_BUCKET = get_env("S3_BUCKET", "metadata-ingestion")
S3_REGION = get_env("S3_REGION", "us-east-1")
