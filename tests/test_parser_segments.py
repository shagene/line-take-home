import pytest

from app.parser import split_segments


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
