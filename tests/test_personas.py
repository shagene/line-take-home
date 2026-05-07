"""Integration tests named for the user behaviors they verify.

The test names function as documentation of who the API is built to serve:
- "Marcus" wants to know what's open right now (current datetime).
- "Priya" wants to plan late-night meals (overnight + Sunday wraparound).
- "Leo" wants to build a frontend on top of the API (response shape, errors).
- "Hannah" wants weekend lunch and is sensitive to dinner-only weekend days.
- "Aiden" wants Saturday breakfast at hours that are weekend-only.
- "Dana" wants Tuesday dinner and is sensitive to mid-week closed days.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.intervals import Interval, Restaurant
from app.parser import parse_hours


def _restaurant(name: str, raw_hours: str) -> Restaurant:
    return Restaurant(name=name, raw_hours=raw_hours, intervals=parse_hours(raw_hours))


@pytest.fixture
def client():
    fake_restaurants = [
        Restaurant(
            name="Day Cafe",
            raw_hours="Mon-Sun 11 am - 10 pm",
            intervals=[
                Interval(d * 1440 + 660, d * 1440 + 22 * 60, "Mon-Sun 11 am - 10 pm")
                for d in range(7)
            ],
        ),
        Restaurant(
            name="Night Owl",
            raw_hours="Fri-Sat 8 pm - 4 am",
            intervals=[
                Interval(4 * 1440 + 20 * 60, 5 * 1440 + 4 * 60, "Fri-Sat 8 pm - 4 am"),
                Interval(5 * 1440 + 20 * 60, 6 * 1440 + 4 * 60, "Fri-Sat 8 pm - 4 am"),
            ],
        ),
        Restaurant(
            name="Sunday Late",
            raw_hours="Sun 8 pm - 2 am",
            intervals=[
                Interval(6 * 1440 + 20 * 60, 10080, "Sun 8 pm - 2 am"),
                Interval(0, 120, "Sun 8 pm - 2 am"),
            ],
        ),
        # Hannah's scenario: a weekend-only dinner spot.
        _restaurant("Weekend Dinner", "Sat 5:30 pm - 11 pm"),
        # Aiden's scenario: weekend-only early breakfast.
        _restaurant("Weekend Brunch", "Sat-Sun 7 am - 3 pm"),
        # Dana's scenario: closed on Tuesday only.
        _restaurant("Skip Tuesday", "Mon, Wed-Sun 11 am - 10 pm"),
    ]
    fake_rows = [(r.name, r.raw_hours) for r in fake_restaurants]
    with patch("app.main.load_csv", return_value=fake_rows), \
         patch("app.main.build_restaurants", return_value=fake_restaurants):
        from app.main import app
        with TestClient(app) as test_client:
            yield test_client


# Marcus: hungry customer, wants "open now"

def test_marcus_open_now_evening(client):
    # Wednesday 7:00 PM
    r = client.get("/api/restaurants/open?datetime=2026-05-06T19:00:00")
    assert r.status_code == 200
    assert "Day Cafe" in r.json()


def test_marcus_returns_empty_when_nothing_open(client):
    # Wednesday 4:00 AM
    r = client.get("/api/restaurants/open?datetime=2026-05-06T04:00:00")
    assert r.status_code == 200
    assert r.json() == []


# Priya: late-night planner

def test_priya_friday_late_night_includes_night_owl(client):
    # Friday 11:30 PM
    r = client.get("/api/restaurants/open?datetime=2026-05-08T23:30:00")
    assert "Night Owl" in r.json()


def test_priya_saturday_one_am_uses_friday_overnight_interval(client):
    # Saturday 01:00 — covered by Friday's overnight (Fri 8 pm - 4 am).
    r = client.get("/api/restaurants/open?datetime=2026-05-09T01:00:00")
    assert "Night Owl" in r.json()


def test_priya_monday_one_am_uses_sunday_wraparound(client):
    # Monday 01:00 — covered by Sunday's wraparound (Sun 8 pm - 2 am).
    r = client.get("/api/restaurants/open?datetime=2026-05-04T01:00:00")
    assert "Sunday Late" in r.json()


# Leo: frontend developer

def test_leo_response_is_sorted_alphabetically(client):
    # Wednesday 7:00 PM — Day Cafe is open; only one match here, so add a
    # broader Wednesday case via the day cafe's interval.
    r = client.get("/api/restaurants/open?datetime=2026-05-06T19:00:00")
    body = r.json()
    assert body == sorted(body)


def test_leo_invalid_datetime_returns_422(client):
    r = client.get("/api/restaurants/open?datetime=tomorrow")
    assert r.status_code == 422


def test_leo_missing_datetime_returns_422(client):
    r = client.get("/api/restaurants/open")
    assert r.status_code == 422


# Hannah: weekend dinner-only diner

def test_hannah_saturday_lunch_excludes_dinner_only_spots(client):
    # Saturday 12:30 PM — Weekend Dinner (Sat 5:30 pm) not open yet; Day Cafe open.
    r = client.get("/api/restaurants/open?datetime=2026-05-09T12:30:00")
    body = r.json()
    assert "Day Cafe" in body
    assert "Weekend Dinner" not in body


def test_hannah_saturday_evening_includes_dinner_only_spots(client):
    # Saturday 7:00 PM — Weekend Dinner is open.
    r = client.get("/api/restaurants/open?datetime=2026-05-09T19:00:00")
    assert "Weekend Dinner" in r.json()


# Aiden: weekend early-bird

def test_aiden_saturday_8am_includes_weekend_brunch(client):
    # Saturday 08:00 — Weekend Brunch (Sat-Sun 7 am - 3 pm) open; Day Cafe (11 am-10 pm) closed.
    r = client.get("/api/restaurants/open?datetime=2026-05-09T08:00:00")
    body = r.json()
    assert "Weekend Brunch" in body
    assert "Day Cafe" not in body


def test_aiden_weekday_8am_excludes_weekend_brunch(client):
    # Wednesday 08:00 — Weekend Brunch is closed (weekends only).
    r = client.get("/api/restaurants/open?datetime=2026-05-06T08:00:00")
    assert "Weekend Brunch" not in r.json()


# Dana: Tuesday-night planner

def test_dana_tuesday_evening_excludes_skip_tuesday(client):
    # Tuesday 19:00 — Skip Tuesday closed; other Tuesday-evening spots still open.
    r = client.get("/api/restaurants/open?datetime=2026-05-05T19:00:00")
    body = r.json()
    assert "Skip Tuesday" not in body
    assert "Day Cafe" in body  # Day Cafe runs Mon-Sun, so this proves the gap is per-day.


def test_dana_wednesday_evening_includes_skip_tuesday(client):
    # Wednesday 19:00 — Skip Tuesday opens Wed-Sun.
    r = client.get("/api/restaurants/open?datetime=2026-05-06T19:00:00")
    assert "Skip Tuesday" in r.json()
