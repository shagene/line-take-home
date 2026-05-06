import pytest

from app.intervals import Interval
from app.parser import build_intervals, parse_segment, split_segments


def test_split_segments_single_returns_one():
    assert split_segments("Mon-Sun 11 am - 10 pm") == ["Mon-Sun 11 am - 10 pm"]


def test_split_segments_two_segments():
    raw = "Mon-Thu 11 am - 10 pm / Fri-Sat 11 am - 12 am"
    assert split_segments(raw) == [
        "Mon-Thu 11 am - 10 pm",
        "Fri-Sat 11 am - 12 am",
    ]


def test_split_segments_three_segments():
    raw = "Mon-Thu 11 am - 11 pm / Fri-Sat 11 am - 12:30 am / Sun 10 am - 11 pm"
    assert split_segments(raw) == [
        "Mon-Thu 11 am - 11 pm",
        "Fri-Sat 11 am - 12:30 am",
        "Sun 10 am - 11 pm",
    ]


def test_split_segments_tolerates_extra_whitespace():
    raw = "Mon-Thu 11 am - 10 pm  /  Fri-Sat 11 am - 12 am"
    assert split_segments(raw) == [
        "Mon-Thu 11 am - 10 pm",
        "Fri-Sat 11 am - 12 am",
    ]


def test_split_segments_rejects_empty_segment():
    with pytest.raises(ValueError):
        split_segments("Mon 11 am - 10 pm //  Tue 5 pm - 11 pm")


def test_parse_segment_simple_day():
    assert parse_segment("Mon 11 am - 10 pm") == ([0], 660, 1320)


def test_parse_segment_simple_range():
    assert parse_segment("Mon-Fri 11 am - 10 pm") == ([0, 1, 2, 3, 4], 660, 1320)


def test_parse_segment_comma_groups():
    assert parse_segment("Mon-Thu, Sun 11:30 am - 10 pm") == ([0, 1, 2, 3, 6], 690, 1320)


def test_parse_segment_overnight_close():
    # Closing time before opening — overnight (handled later in build_intervals).
    assert parse_segment("Mon 5 pm - 1:30 am") == ([0], 1020, 90)


def test_parse_segment_rejects_missing_dash():
    with pytest.raises(ValueError):
        parse_segment("Mon 11 am 10 pm")


def test_build_intervals_same_day_single():
    intervals = build_intervals([0], 660, 1320, "Mon 11 am - 10 pm")
    assert intervals == [Interval(660, 1320, "Mon 11 am - 10 pm")]


def test_build_intervals_same_day_multiple():
    intervals = build_intervals([0, 1, 2], 660, 1320, "Mon-Wed 11 am - 10 pm")
    assert intervals == [
        Interval(660, 1320, "Mon-Wed 11 am - 10 pm"),
        Interval(2100, 2760, "Mon-Wed 11 am - 10 pm"),
        Interval(3540, 4200, "Mon-Wed 11 am - 10 pm"),
    ]


def test_build_intervals_overnight_simple():
    # Mon 5 pm - 1:30 am → Monday 17:00 → Tuesday 01:30
    intervals = build_intervals([0], 1020, 90, "Mon 5 pm - 1:30 am")
    assert intervals == [Interval(1020, 1530, "Mon 5 pm - 1:30 am")]


def test_build_intervals_overnight_all_week():
    # Seoul 116 case: Mon-Sun 11 am - 4 am.
    intervals = build_intervals([0, 1, 2, 3, 4, 5], 660, 240, "Mon-Sat 11 am - 4 am")
    expected = [
        Interval(660, 1680, "Mon-Sat 11 am - 4 am"),     # Mon 11:00 → Tue 04:00
        Interval(2100, 3120, "Mon-Sat 11 am - 4 am"),    # Tue 11:00 → Wed 04:00
        Interval(3540, 4560, "Mon-Sat 11 am - 4 am"),    # Wed 11:00 → Thu 04:00
        Interval(4980, 6000, "Mon-Sat 11 am - 4 am"),    # Thu 11:00 → Fri 04:00
        Interval(6420, 7440, "Mon-Sat 11 am - 4 am"),    # Fri 11:00 → Sat 04:00
        Interval(7860, 8880, "Mon-Sat 11 am - 4 am"),    # Sat 11:00 → Sun 04:00
    ]
    assert intervals == expected
