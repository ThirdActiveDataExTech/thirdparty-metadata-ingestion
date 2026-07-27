from src.collectors.naver_datalab_scale import compute_inter_scale, median_ratio


def test_median_ratio_no_overlap_returns_1():
    assert median_ratio({"2026-01-01": 50}, {"2026-01-02": 40}) == 1.0


def test_median_ratio_single_overlap():
    # a/b = 50/25 = 2.0
    assert median_ratio({"2026-01-01": 50}, {"2026-01-01": 25}) == 2.0


def test_median_ratio_odd_count_uses_middle_value():
    a = {"d1": 10, "d2": 20, "d3": 30}
    b = {"d1": 10, "d2": 10, "d3": 10}
    # ratios = [1.0, 2.0, 3.0] -> median = 2.0
    assert median_ratio(a, b) == 2.0


def test_median_ratio_even_count_averages_middle_two():
    a = {"d1": 10, "d2": 20, "d3": 30, "d4": 40}
    b = {"d1": 10, "d2": 10, "d3": 10, "d4": 10}
    # ratios sorted = [1.0, 2.0, 3.0, 4.0] -> avg(2.0, 3.0) = 2.5
    assert median_ratio(a, b) == 2.5


def test_median_ratio_ignores_zero_or_negative_values():
    a = {"d1": 10, "d2": 0}
    b = {"d1": 10, "d2": 5}
    # d2 skipped (a value is 0) -> only d1: 10/10 = 1.0
    assert median_ratio(a, b) == 1.0


def test_compute_inter_scale_first_collection_returns_1():
    assert compute_inter_scale({}, {"2026-01-01": 50}) == 1.0
    assert compute_inter_scale({"2026-01-01": 50}, {}) == 1.0


def test_compute_inter_scale_uses_overlapping_periods_only():
    existing = {"2026-01-01": 100, "2026-01-02": 50}
    new = {"2026-01-01": 50, "2026-01-03": 999}  # 01-03 has no counterpart in existing
    # overlap: 01-01 -> 100/50 = 2.0
    assert compute_inter_scale(existing, new) == 2.0
