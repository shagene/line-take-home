from app.intervals import Interval
from app.parser import parse_hours


def test_parse_hours_single_segment():
    intervals = parse_hours("Mon-Sun 11:00 am - 10 pm")
    assert len(intervals) == 7
    assert all(i.start_week_minute % 1440 == 660 for i in intervals)
    assert all((i.end_week_minute - 1) % 1440 == 22 * 60 - 1 for i in intervals)


def test_parse_hours_multiple_segments():
    intervals = parse_hours(
        "Mon-Thu, Sun 11:30 am - 10 pm / Fri-Sat 11:30 am - 11 pm"
    )
    days_seen = sorted({i.start_week_minute // 1440 for i in intervals})
    assert days_seen == [0, 1, 2, 3, 4, 5, 6]
    assert len(intervals) == 7


def test_parse_hours_with_overnight_segment():
    intervals = parse_hours("Mon-Wed 5 pm - 12:30 am")
    # Each Mon, Tue, Wed → overnight interval ending the next day.
    assert len(intervals) == 3
    for i in intervals:
        assert i.end_week_minute - i.start_week_minute == (24 * 60 - 17 * 60) + 30


def test_parse_hours_omitted_day_produces_no_interval():
    intervals = parse_hours("Mon, Wed-Sun 11 am - 10 pm")
    days_seen = sorted({i.start_week_minute // 1440 for i in intervals})
    # Tuesday (1) is omitted.
    assert days_seen == [0, 2, 3, 4, 5, 6]


def test_parse_hours_closes_at_midnight_means_end_of_day():
    intervals = parse_hours("Mon-Sun 5 pm - 12 am")
    assert len(intervals) == 7
    for i in intervals:
        # Each interval should close exactly at the next day's midnight.
        day = i.start_week_minute // 1440
        assert i.start_week_minute == day * 1440 + 17 * 60
        expected_end = 10080 if day == 6 else (day + 1) * 1440
        assert i.end_week_minute == expected_end
