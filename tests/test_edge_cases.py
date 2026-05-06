"""Explicit edge case tests covering each case named in approach-recommended.md."""

import pytest

from app.intervals import Interval, find_open
from app.parser import parse_hours


def _open_at(intervals: list[Interval], q: int) -> bool:
    return any(i.start_week_minute <= q < i.end_week_minute for i in intervals)


# Boundary semantics

def test_boundary_open_exactly_at_opening_minute():
    intervals = parse_hours("Mon 11 am - 10 pm")
    # Monday 11:00 = week-minute 660
    assert _open_at(intervals, 660) is True


def test_boundary_closed_exactly_at_closing_minute():
    intervals = parse_hours("Mon 11 am - 10 pm")
    # Monday 22:00 = week-minute 22 * 60 = 1320
    assert _open_at(intervals, 1320) is False


def test_boundary_open_one_minute_before_closing():
    intervals = parse_hours("Mon 11 am - 10 pm")
    assert _open_at(intervals, 1319) is True


# Overnight

def test_overnight_open_after_midnight():
    intervals = parse_hours("Mon 5 pm - 1:30 am")
    # Tuesday 01:00 = 1440 + 60 = 1500
    assert _open_at(intervals, 1500) is True


def test_overnight_closed_at_close_time():
    intervals = parse_hours("Mon 5 pm - 1:30 am")
    # Tuesday 01:30 = 1440 + 90 = 1530
    assert _open_at(intervals, 1530) is False


# All-week overnight (Seoul 116)

def test_all_week_overnight_tuesday_2am_is_open():
    intervals = parse_hours("Mon-Sun 11 am - 4 am")
    # Tuesday 02:00 = 1440 + 120 = 1560 — covered by Monday's interval.
    assert _open_at(intervals, 1560) is True


def test_all_week_overnight_tuesday_5am_is_closed():
    intervals = parse_hours("Mon-Sun 11 am - 4 am")
    # Tuesday 05:00 = 1440 + 300 = 1740 — Monday's interval ended at 04:00.
    assert _open_at(intervals, 1740) is False


# Sunday-to-Monday wraparound

def test_sunday_wraparound_monday_one_am_is_open():
    intervals = parse_hours("Sun 8 pm - 2 am")
    # Monday 01:00 = week-minute 60 — covered by the wraparound split.
    assert _open_at(intervals, 60) is True


def test_sunday_wraparound_monday_two_am_is_closed():
    intervals = parse_hours("Sun 8 pm - 2 am")
    # Monday 02:00 = week-minute 120 — exactly at the close, half-open says closed.
    assert _open_at(intervals, 120) is False


# 12 am / 12 pm conversions and closing-at-12am rule

def test_closes_at_midnight_means_end_of_day():
    intervals = parse_hours("Mon-Sun 5 pm - 12 am")
    # Monday 23:59 should still be open. Monday 23:59 = 23*60+59 = 1439.
    assert _open_at(intervals, 1439) is True


def test_closes_at_midnight_then_closed_at_next_day_start():
    intervals = parse_hours("Mon-Sat 5 pm - 12 am")  # not Sunday — avoid wraparound
    # Tuesday 00:00 = 1440 — closed (half-open semantics).
    assert _open_at(intervals, 1440) is False


def test_12_pm_is_noon():
    intervals = parse_hours("Mon 12 pm - 11 pm")
    # Monday 12:00 noon = 720
    assert _open_at(intervals, 720) is True
    # Monday 11:59 = 719 — closed (before opening)
    assert _open_at(intervals, 719) is False


# Omitted days

def test_omitted_day_produces_no_interval():
    intervals = parse_hours("Mon, Wed-Sun 11 am - 10 pm")
    days_with_intervals = sorted({i.start_week_minute // 1440 for i in intervals})
    assert 1 not in days_with_intervals  # Tuesday absent


# Circular ranges

def test_circular_day_range_fri_mon():
    intervals = parse_hours("Fri-Mon 5 pm - 11 pm")
    days_with_intervals = sorted({i.start_week_minute // 1440 for i in intervals})
    assert days_with_intervals == [0, 4, 5, 6]  # Mon, Fri, Sat, Sun
