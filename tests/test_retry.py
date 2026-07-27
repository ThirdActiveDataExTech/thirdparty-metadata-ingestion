import pytest

from src.common.retry import RetryableError, with_retry


def test_with_retry_returns_result_on_first_success():
    calls = []

    def fn():
        calls.append(1)
        return "ok"

    assert with_retry(fn, max_attempts=3, base_delay=0) == "ok"
    assert len(calls) == 1


def test_with_retry_retries_on_retryable_error_then_succeeds():
    calls = []

    def fn():
        calls.append(1)
        if len(calls) < 2:
            raise RetryableError("transient")
        return "ok"

    assert with_retry(fn, max_attempts=3, base_delay=0) == "ok"
    assert len(calls) == 2


def test_with_retry_raises_after_max_attempts():
    def fn():
        raise RetryableError("always fails")

    with pytest.raises(RetryableError):
        with_retry(fn, max_attempts=3, base_delay=0)


def test_with_retry_does_not_retry_non_retryable_errors():
    calls = []

    def fn():
        calls.append(1)
        raise ValueError("not retryable")

    with pytest.raises(ValueError):
        with_retry(fn, max_attempts=3, base_delay=0)
    assert len(calls) == 1
