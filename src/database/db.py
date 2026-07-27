"""DB 커넥션 헬퍼 — scripts/embed_*.py와 동일한 psycopg2 연결 패턴."""

import psycopg2
from src.common import config


def get_conn():
    return psycopg2.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
    )
