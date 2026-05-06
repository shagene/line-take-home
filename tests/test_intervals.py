from datetime import datetime

import pytest

from app.intervals import (
    Interval,
    Restaurant,
    WEEK_MINUTES,
    datetime_to_week_minute,
    find_open,
    to_week_minute,
)


def test_week_minutes_constant():
    assert WEEK_MINUTES == 7 * 24 * 60 == 10080


@pytest.mark.parametrize("day_index, minute_of_day, expected", [
    (0, 0, 0),
    (0, 660, 660),
    (1, 0, 1440),
    (2, 0, 2880),
    (6, 0, 8640),
    (6, 1439, 10079),
])
def test_to_week_minute(day_index, minute_of_day, expected):
    assert to_week_minute(day_index, minute_of_day) == expected


@pytest.mark.parametrize("dt, expected", [
    (datetime(2026, 5, 4, 0, 0), 0),       # Monday 00:00
    (datetime(2026, 5, 4, 11, 0), 660),    # Monday 11:00
    (datetime(2026, 5, 6, 21, 30), 4170),  # Wednesday 21:30
    (datetime(2026, 5, 10, 23, 59), 10079),  # Sunday 23:59
])
def test_datetime_to_week_minute(dt, expected):
    assert datetime_to_week_minute(dt) == expected


def _make_restaurant(name: str, intervals: list[tuple[int, int]]) -> Restaurant:
    return Restaurant(
        name=name,
        raw_hours="<test>",
        intervals=[Interval(s, e, "<test>") for s, e in intervals],
    )


def test_find_open_returns_sorted_names_for_matching_intervals():
    restaurants = [
        _make_restaurant("B", [(0, 1440)]),
        _make_restaurant("A", [(0, 1440)]),
        _make_restaurant("C", [(2000, 3000)]),
    ]
    assert find_open(restaurants, 600) == ["A", "B"]


def test_find_open_excludes_at_closing_minute():
    restaurants = [_make_restaurant("X", [(660, 1320)])]
    assert find_open(restaurants, 1320) == []


def test_find_open_includes_at_opening_minute():
    restaurants = [_make_restaurant("X", [(660, 1320)])]
    assert find_open(restaurants, 660) == ["X"]


def test_find_open_empty_when_no_match():
    restaurants = [_make_restaurant("X", [(0, 100)])]
    assert find_open(restaurants, 5000) == []
