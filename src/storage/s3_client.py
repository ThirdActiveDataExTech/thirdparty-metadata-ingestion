"""SeaweedFS(S3 호환) 클라이언트 — infrastructure/04_ObjectStorage.md의 접속 정보 사용.

architecture/05_Object_Storage_Export.md §5 결정에 따라, 이 모듈의 업로드 함수들은
실패 시 예외를 그대로 올린다(삼키지 않음) — 예외를 삼켜서 "수집 자체는 성공 처리"하는
판단은 호출부(파이프라인)의 책임이지 이 모듈의 책임이 아니다.
"""

import json
from typing import Any, Dict

import boto3
from botocore.config import Config

from src.common import config

_client = None


def get_s3_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=config.S3_ENDPOINT,
            aws_access_key_id=config.S3_ACCESS_KEY,
            aws_secret_access_key=config.S3_SECRET_KEY,
            region_name=config.S3_REGION,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
    return _client


def upload_text(key: str, text: str) -> None:
    get_s3_client().put_object(
        Bucket=config.S3_BUCKET, Key=key, Body=text.encode("utf-8"), ContentType="text/plain; charset=utf-8"
    )


def upload_json(key: str, obj: Dict[str, Any]) -> None:
    body = json.dumps(obj, ensure_ascii=False, indent=2)
    get_s3_client().put_object(
        Bucket=config.S3_BUCKET, Key=key, Body=body.encode("utf-8"), ContentType="application/json; charset=utf-8"
    )
