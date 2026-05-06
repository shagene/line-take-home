import pytest

from app.parser import expand_days


@pytest.mark.parametrize("input_str, expected", [
    ("Mon", [0]),
    ("Tue", [1]),
    ("Tues", [1]),
    ("Wed", [2]),
    ("Thu", [3]),
    ("Thurs", [3]),
    ("Fri", [4]),
    ("Sat", [5]),
    ("Sun", [6]),
    ("Monday", [0]),
    ("Sunday", [6]),
])
def test_expand_days_single_tokens(input_str, expected):
    assert expand_days(input_str) == expected


@pytest.mark.parametrize("input_str, expected", [
    ("Mon-Fri", [0, 1, 2, 3, 4]),
    ("Sat-Sun", [5, 6]),
    ("Mon-Sun", [0, 1, 2, 3, 4, 5, 6]),
    ("Tues-Thurs", [1, 2, 3]),
])
def test_expand_days_simple_ranges(input_str, expected):
    assert expand_days(input_str) == expected


def test_expand_days_rejects_unknown_token():
    with pytest.raises(ValueError):
        expand_days("Funday")
