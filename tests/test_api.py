from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.intervals import Interval, Restaurant


@pytest.fixture
def client_with_fixture():
    """A TestClient whose startup loads a small in-memory fixture, not the real CSV."""
    fake_restaurants = [
        Restaurant(
            name="Test Cafe",
            raw_hours="Mon-Fri 7 am - 3 pm",
            intervals=[
                Interval(420, 900, "Mon-Fri 7 am - 3 pm"),       # Mon 07:00 → 15:00
                Interval(420 + 1440, 900 + 1440, "Mon-Fri 7 am - 3 pm"),
            ],
        ),
        Restaurant(
            name="Late Bar",
            raw_hours="Mon 5 pm - 1 am",
            intervals=[
                Interval(1020, 1500, "Mon 5 pm - 1 am"),         # Mon 17:00 → Tue 01:00
            ],
        ),
    ]
    fake_rows = [(r.name, r.raw_hours) for r in fake_restaurants]
    with patch("app.main.load_csv", return_value=fake_rows), \
         patch("app.main.build_restaurants", return_value=fake_restaurants):
        from app.main import app
        with TestClient(app) as client:
            yield client


def test_api_returns_list_of_open_names(client_with_fixture):
    # 2026-05-04 is a Monday.
    r = client_with_fixture.get("/api/restaurants/open?datetime=2026-05-04T08:00:00")
    assert r.status_code == 200
    assert r.json() == ["Test Cafe"]


def test_api_returns_empty_list_when_nothing_open(client_with_fixture):
    r = client_with_fixture.get("/api/restaurants/open?datetime=2026-05-04T05:00:00")
    assert r.status_code == 200
    assert r.json() == []


def test_api_includes_overnight_match(client_with_fixture):
    # Monday 22:30 — Late Bar is mid-overnight interval.
    r = client_with_fixture.get("/api/restaurants/open?datetime=2026-05-04T22:30:00")
    assert r.status_code == 200
    assert "Late Bar" in r.json()


def test_api_invalid_datetime_returns_422(client_with_fixture):
    r = client_with_fixture.get("/api/restaurants/open?datetime=not-a-date")
    assert r.status_code == 422


def test_api_missing_datetime_returns_422(client_with_fixture):
    r = client_with_fixture.get("/api/restaurants/open")
    assert r.status_code == 422
