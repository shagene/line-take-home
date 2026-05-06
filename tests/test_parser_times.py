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
