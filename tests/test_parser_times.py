import pytest

from app.parser import parse_time


@pytest.mark.parametrize("input_str, expected", [
    ("11 am", 660),
    ("10 pm", 1320),
    ("1 am", 60),
    ("9 pm", 21 * 60),
])
def test_parse_time_simple_hours(input_str, expected):
    assert parse_time(input_str) == expected


@pytest.mark.parametrize("input_str, expected", [
    ("11:30 am", 690),
    ("11:00 am", 660),
    ("10:30 pm", 22 * 60 + 30),
    ("1:30 am", 90),
    ("12:30 pm", 12 * 60 + 30),
])
def test_parse_time_with_minutes(input_str, expected):
    assert parse_time(input_str) == expected


@pytest.mark.parametrize("input_str, expected", [
    ("12 am", 0),
    ("12 pm", 720),
    ("12:00 am", 0),
    ("12:00 pm", 720),
    ("12:30 am", 30),
    ("12:30 pm", 750),
])
def test_parse_time_handles_12_am_and_12_pm(input_str, expected):
    assert parse_time(input_str) == expected


def test_parse_time_rejects_garbage():
    with pytest.raises(ValueError):
        parse_time("not a time")
