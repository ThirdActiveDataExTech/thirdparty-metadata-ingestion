"""컨테이너 CPU 상한에 맞춘 스레드 수 (src/common/cpu.py, 2026-11-11).

2코어 상한 파드에서 torch가 노드 코어 수(8)만큼 스레드를 띄워 임베딩이 2배 느렸다.
"""

import pytest

from src.common import cpu


def _v2(tmp_path, text):
    (tmp_path / "cpu.max").write_text(text)
    return tmp_path


def _v1(tmp_path, quota, period="100000"):
    d = tmp_path / "cpu"
    d.mkdir()
    (d / "cpu.cfs_quota_us").write_text(quota)
    (d / "cpu.cfs_period_us").write_text(period)
    return tmp_path


@pytest.mark.parametrize("text,limit", [("200000 100000", 2), ("150000 100000", 2), ("50000 100000", 1),
                                        ("max 100000", None)])
def test_cgroup_v2(tmp_path, text, limit):
    assert cpu.cpu_limit(_v2(tmp_path, text)) == limit


@pytest.mark.parametrize("quota,limit", [("200000", 2), ("-1", None)])
def test_cgroup_v1(tmp_path, quota, limit):
    assert cpu.cpu_limit(_v1(tmp_path, quota)) == limit


def test_상한을_모르면_None(tmp_path):
    assert cpu.cpu_limit(tmp_path) is None
    assert cpu.cpu_limit(_v2(tmp_path, "깨진 값")) is None


def test_스레드는_기본값과_상한_중_작은_쪽(tmp_path):
    root = _v2(tmp_path, "200000 100000")
    assert cpu.threads(8, root=root) == 2
    assert cpu.threads(1, root=root) == 1


def test_상한이_없으면_기본값(tmp_path):
    assert cpu.threads(8, root=tmp_path) == 8


def test_환경변수가_있으면_그_값(tmp_path, monkeypatch):
    monkeypatch.setenv("EMBEDDING_THREADS", "3")
    assert cpu.threads(8, env="EMBEDDING_THREADS", root=_v2(tmp_path, "200000 100000")) == 3
    monkeypatch.setenv("EMBEDDING_THREADS", "abc")       # 이상한 값이면 무시하고 상한을 따른다
    assert cpu.threads(8, env="EMBEDDING_THREADS", root=tmp_path) == 2
