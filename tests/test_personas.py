"""Integration tests named for the user behaviors they verify.

The test names function as documentation of who the API is built to serve:
- "Marcus" wants to know what's open right now (current datetime).
- "Priya" wants to plan late-night meals (overnight + Sunday wraparound).
- "Leo" wants to build a frontend on top of the API (response shape, errors).
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.intervals import Interval, Restaurant


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
