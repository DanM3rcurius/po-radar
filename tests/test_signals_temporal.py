from datetime import datetime, timedelta, timezone

import pytest

from poradar.signals import burst_ratio

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def ago(hours: float) -> datetime:
    return NOW - timedelta(hours=hours)


def test_fewer_than_three_items_is_never_a_burst():
    assert burst_ratio([], NOW) == 0.0
    assert burst_ratio([ago(1)], NOW) == 0.0
    assert burst_ratio([ago(1), ago(2)], NOW) == 0.0


def test_steady_trickle_is_not_a_burst():
    # One item per six-hour window across the whole baseline, one in the window.
    times = [ago(h) for h in range(1, 72, 6)]
    assert burst_ratio(times, NOW) < 0.3


def test_synchronized_push_saturates():
    times = [ago(h) for h in (0.2, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0)]
    times += [ago(30), ago(50)]  # a thin trailing baseline
    assert burst_ratio(times, NOW) == pytest.approx(1.0)


def test_exactly_four_times_the_baseline_rate_saturates():
    # Baseline: 11 windows of (72 - 6) hours, 11 items -> rate 1.0 per window.
    trailing = [ago(6 + 6 * i + 1) for i in range(11)]
    assert burst_ratio(trailing + [ago(1), ago(2), ago(3)], NOW) == pytest.approx(0.75)
    assert burst_ratio(trailing + [ago(h) for h in (1, 2, 3, 4)], NOW) == pytest.approx(1.0)
    assert burst_ratio(trailing + [ago(h) for h in (1, 2, 3, 4, 5)], NOW) == pytest.approx(1.0)


def test_nothing_recent_is_zero_even_with_history():
    times = [ago(h) for h in (8, 12, 20, 30, 40, 60)]
    assert burst_ratio(times, NOW) == 0.0


def test_no_trailing_history_reads_as_a_full_burst():
    assert burst_ratio([ago(1), ago(2), ago(3)], NOW) == pytest.approx(1.0)


def test_items_older_than_the_baseline_are_ignored():
    stale = [ago(200), ago(300), ago(400)]
    assert burst_ratio(stale + [ago(1), ago(2), ago(3)], NOW) == pytest.approx(1.0)


def test_future_timestamps_are_ignored():
    times = [NOW + timedelta(hours=5), ago(20), ago(30), ago(40)]
    assert burst_ratio(times, NOW) == 0.0


def test_naive_datetimes_are_read_as_utc():
    naive = [ago(1).replace(tzinfo=None), ago(2).replace(tzinfo=None), ago(3).replace(tzinfo=None)]
    assert burst_ratio(naive, NOW) == pytest.approx(1.0)
    assert burst_ratio(naive, NOW.replace(tzinfo=None)) == pytest.approx(1.0)


def test_other_timezones_are_normalised():
    tz = timezone(timedelta(hours=-7))
    times = [ago(1).astimezone(tz), ago(2).astimezone(tz), ago(3).astimezone(tz)]
    assert burst_ratio(times, NOW) == pytest.approx(1.0)


def test_windows_are_configurable_and_validated():
    times = [ago(0.5), ago(0.8), ago(1.5), ago(20), ago(40)]
    assert burst_ratio(times, NOW, window_hours=2, baseline_hours=48) > 0.0
    with pytest.raises(ValueError):
        burst_ratio(times, NOW, window_hours=0)
    with pytest.raises(ValueError):
        burst_ratio(times, NOW, window_hours=6, baseline_hours=6)


def test_result_is_always_bounded():
    times = [ago(i * 0.01) for i in range(200)] + [ago(70)]
    assert 0.0 <= burst_ratio(times, NOW) <= 1.0
