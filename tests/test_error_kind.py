"""수집 실패 원인 분류 — 실제로 남았던 오류 문구에서 출발한다."""

import pytest

from src.common.error_kind import classify_error, for_user


@pytest.mark.parametrize("text,kind", [
    # 2026-10 말 실제 실패(dcat_provenance)
    ("HTTPSConnectionPool(host='blog.like.naver.com', port=443): Read timed out. (read timeout=10)", "transient"),
    # 2026-11-09 감시 중 로컬에서 난 DB 끊김 — 'timed out'이 있어도 DB다(순서 규칙)
    ("psycopg2.OperationalError: could not receive data from server: Operation timed out", "db"),
    ("HTTPError: 403 Client Error: Forbidden for url: https://www.googleapis.com/youtube/v3/search", "auth"),
    ("{'error': {'errors': [{'reason': 'quotaExceeded'}]}}", "quota"),
    ("429 Client Error: Too Many Requests", "quota"),
    ("HTTPError: 401 Client Error: Unauthorized", "auth"),
    ("503 Server Error: Service Unavailable", "transient"),
    ("botocore.exceptions.EndpointConnectionError: Could not connect", "storage"),
    ("OSError: We couldn't connect to 'https://huggingface.co' to load this file", "model"),
    ("Container was OOMKilled", "oom"),
    ("KeyError: 'items'", "unknown"),
])
def test_원인_분류(text, kind):
    assert classify_error(text)["kind"] == kind


def test_맨_숫자는_HTTP_코드로_읽지_않는다():
    """'반영 429행'이 호출 한도 초과로 보이면 안 된다."""
    assert classify_error("ValueError: 반영 429행 중 403번째 행 형식 오류")["kind"] == "unknown"


@pytest.mark.parametrize("empty", [None, "", "   "])
def test_오류가_없으면_분류도_없다(empty):
    assert classify_error(empty) is None and for_user(empty) is None


def test_사용자용에는_원문이_없다():
    raw = "psycopg2.OperationalError: could not connect to server at 10.0.0.5:5432"
    u = for_user(raw)
    assert set(u) == {"kind", "label", "message", "user_action"}
    assert "10.0.0.5" not in str(u)


def test_사용자가_고칠_일은_키_문제뿐이다():
    assert for_user("401 Unauthorized")["user_action"] is True
    assert for_user("Read timed out")["user_action"] is False


def test_스케줄러가_수거한_중단은_메모리_부족보다_먼저_잡는다():
    # 문구에 '메모리 부족'이 있어도 '실행 중단'으로 — 죽은 이유는 DB만으로 단정할 수 없다
    from scripts.scheduler_tick import INTERRUPTED_MSG
    assert classify_error(INTERRUPTED_MSG)["kind"] == "interrupted"
