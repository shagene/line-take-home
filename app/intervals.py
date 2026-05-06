"""Interval types and week-minute helpers.

The week is encoded as a single integer in [0, 10080):
  Monday 00:00 = 0
  Tuesday 00:00 = 1440
  ...
  Sunday 23:59 = 10079

This collapses the open/closed check to a single integer-range comparison.
Intervals are half-open [start, end).
"""

from dataclasses import dataclass
from datetime import datetime

WEEK_MINUTES = 10080  # 7 * 24 * 60


@dataclass(frozen=True)
class Interval:
    start_week_minute: int
    end_week_minute: int
    source_segment: str


@dataclass
class Restaurant:
    name: str
    raw_hours: str
    intervals: list[Interval]


def to_week_minute(day_index: int, minute_of_day: int) -> int:
    """Convert (day_index 0..6, minute_of_day 0..1439) → week-minute 0..10079."""
    return day_index * 1440 + minute_of_day


def datetime_to_week_minute(dt: datetime) -> int:
    """Convert a naive datetime to a query week-minute (Monday=0)."""
    return to_week_minute(dt.weekday(), dt.hour * 60 + dt.minute)


def find_open(restaurants: list[Restaurant], q: int) -> list[str]:
    """Return the sorted names of restaurants with any interval matching q.

    A restaurant matches if any of its intervals satisfies start <= q < end.
    """
    return sorted(
        r.name
        for r in restaurants
        if any(i.start_week_minute <= q < i.end_week_minute for i in r.intervals)
    )
