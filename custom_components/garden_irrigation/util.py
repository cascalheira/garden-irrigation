"""Helper utilities for Garden Irrigation: scheduling math and overlap detection."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .const import (
    CONF_DAYS,
    CONF_DURATION,
    CONF_NAME,
    CONF_SCHEDULES,
    CONF_TIME,
    WEEKDAYS,
    WEEKDAY_LABELS,
)


def parse_time(value: str) -> tuple[int, int]:
    """Parse a 'HH:MM' or 'HH:MM:SS' time string into (hour, minute)."""
    parts = value.split(":")
    return int(parts[0]), int(parts[1])


def format_days(days: list[str]) -> str:
    """Return a short, human readable representation of selected weekdays."""
    if not days or set(days) == set(WEEKDAYS):
        return "Every day"
    ordered = [d for d in WEEKDAYS if d in days]
    return ", ".join(WEEKDAY_LABELS[d][:3] for d in ordered)


def compute_next_run(
    schedules: list[dict[str, Any]], now: datetime
) -> datetime | None:
    """Return the next datetime any of the given schedules will fire after ``now``."""
    best: datetime | None = None
    for sched in schedules:
        hour, minute = parse_time(sched[CONF_TIME])
        days = sched.get(CONF_DAYS) or WEEKDAYS
        # Look ahead up to 8 days to cover the full weekly cycle.
        for offset in range(8):
            candidate_date = (now + timedelta(days=offset)).date()
            weekday = WEEKDAYS[candidate_date.weekday()]
            if weekday not in days:
                continue
            candidate = now.replace(
                year=candidate_date.year,
                month=candidate_date.month,
                day=candidate_date.day,
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )
            if candidate <= now:
                continue
            if best is None or candidate < best:
                best = candidate
            break
    return best


def _zone_windows(zone: dict[str, Any]):
    """Yield (weekday, start_min, end_min, label) windows for a zone's schedules."""
    duration = int(zone.get(CONF_DURATION, 0))
    for sched in zone.get(CONF_SCHEDULES, []):
        hour, minute = parse_time(sched[CONF_TIME])
        start = hour * 60 + minute
        end = start + duration
        days = sched.get(CONF_DAYS) or WEEKDAYS
        label = f"{zone[CONF_NAME]} @ {sched[CONF_TIME][:5]}"
        for day in days:
            if day in WEEKDAYS:
                yield day, start, end, label


def compute_overlaps(zones: list[dict[str, Any]]) -> list[str]:
    """Return human readable descriptions of schedules whose run windows overlap.

    A window is ``[start, start + duration)`` in minutes from midnight. Two
    windows overlap when they share a weekday and their minute ranges intersect.
    """
    windows = []
    for zone in zones:
        windows.extend(_zone_windows(zone))

    seen: set[tuple[str, str, str]] = set()
    overlaps: list[str] = []
    for i in range(len(windows)):
        day_a, start_a, end_a, label_a = windows[i]
        for j in range(i + 1, len(windows)):
            day_b, start_b, end_b, label_b = windows[j]
            if day_a != day_b:
                continue
            if start_a < end_b and start_b < end_a:
                key = tuple(sorted((label_a, label_b)) + [day_a])
                if key in seen:
                    continue
                seen.add(key)
                overlaps.append(
                    f"{label_a} and {label_b} on {WEEKDAY_LABELS[day_a]}"
                )
    return overlaps
