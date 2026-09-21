"""Burst detection: publication volume in the last window vs its trailing baseline."""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = ["burst_ratio"]

MIN_ITEMS = 3
SATURATION = 4.0  # 4x the baseline rate reads as a full burst


def _as_utc(moment: datetime) -> datetime:
    """Naive datetimes are read as UTC so mixed inputs stay comparable."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def burst_ratio(
    times: list[datetime],
    now: datetime,
    window_hours: float = 6.0,
    baseline_hours: float = 72.0,
) -> float:
    """Share of a synchronized push, in [0, 1].

    Compares the item count in the last ``window_hours`` against the mean
    per-window count over the trailing baseline (the older part of
    ``baseline_hours``). Returns 0.0 for fewer than three items, and saturates
    at 1.0 when the recent window carries at least ``SATURATION`` times the
    baseline rate.
    """
    if window_hours <= 0 or baseline_hours <= window_hours:
        raise ValueError("baseline_hours must be greater than window_hours > 0")
    stamps = [_as_utc(t) for t in times if t is not None]
    if len(stamps) < MIN_ITEMS:
        return 0.0

    ref = _as_utc(now)
    window_seconds = window_hours * 3600.0
    baseline_seconds = baseline_hours * 3600.0

    recent = 0
    trailing = 0
    for stamp in stamps:
        age = (ref - stamp).total_seconds()
        if age < 0:
            continue
        if age <= window_seconds:
            recent += 1
        elif age <= baseline_seconds:
            trailing += 1

    if recent == 0:
        return 0.0

    windows = (baseline_seconds - window_seconds) / window_seconds
    baseline_rate = trailing / windows if windows > 0 else 0.0
    if baseline_rate <= 0.0:
        # Nothing before the window: any qualifying cluster is fully bursty.
        return 1.0 if recent >= MIN_ITEMS else recent / MIN_ITEMS
    ratio = recent / baseline_rate
    return max(0.0, min(1.0, ratio / SATURATION))
