from pathlib import Path

import pytest

from app.loader import build_restaurants, load_csv

FIXTURE = Path(__file__).parent / "fixtures" / "sample.csv"


def test_load_csv_returns_name_hours_tuples():
    rows = load_csv(str(FIXTURE))
    assert rows == [
        ("Test Cafe", "Mon-Fri 7 am - 3 pm"),
        ("Late Bar", "Sun-Thu 5 pm - 12 am  / Fri-Sat 5 pm - 2 am"),
    ]


def test_load_csv_skips_header():
    rows = load_csv(str(FIXTURE))
    assert rows[0][0] != "Restaurant Name"


def test_build_restaurants_parses_hours():
    rows = [("Test Cafe", "Mon-Fri 7 am - 3 pm")]
    restaurants = build_restaurants(rows)
    assert len(restaurants) == 1
    r = restaurants[0]
    assert r.name == "Test Cafe"
    assert r.raw_hours == "Mon-Fri 7 am - 3 pm"
    assert len(r.intervals) == 5  # Monday through Friday


REAL_CSV = Path(__file__).parent.parent / "restaurants.csv"


@pytest.mark.skipif(not REAL_CSV.exists(), reason="real CSV not present in this environment")
def test_real_csv_parses_without_errors():
    rows = load_csv(str(REAL_CSV))
    assert len(rows) == 40  # The take-home CSV has 40 restaurants.
    restaurants = build_restaurants(rows)
    assert len(restaurants) == 40
    # Every restaurant should produce at least one interval.
    for r in restaurants:
        assert r.intervals, f"{r.name!r} parsed to zero intervals"
