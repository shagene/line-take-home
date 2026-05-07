"""Regression tests against the actual restaurants.csv.

Each test pins down a specific row whose schedule shape exposes a class of bug:
- Beasley's: a literal "12 pm" close that means noon, not midnight.
- 42nd Street Oyster Bar: Sunday's segment wraps into Monday morning.
- Seoul 116: every day's interval wraps past midnight (all-week overnight).
- The Cheesecake Factory: Friday's interval ends at exactly 12:30 am Saturday.

If any of these break, the parser, interval engine, or query layer regressed
on a real-world schedule shape — not just a synthetic edge case.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.loader import build_restaurants, load_csv

REAL_CSV = Path(__file__).parent.parent / "restaurants.csv"


@pytest.fixture
def client():
    if not REAL_CSV.exists():
        pytest.skip("real CSV not present")
    rows = load_csv(str(REAL_CSV))
    restaurants = build_restaurants(rows)
    with patch("app.main.load_csv", return_value=rows), \
         patch("app.main.build_restaurants", return_value=restaurants):
        from app.main import app
        with TestClient(app) as test_client:
            yield test_client


# Beasley's Chicken + Honey: "Mon-Fri, Sat 11 am - 12 pm  / Sun 11 am - 10 pm"
# The 12 pm close is NOON (not midnight). Catches a parser that treats 12 pm as 00:00.

def test_beasleys_open_at_11am_monday(client):
    # 2026-05-04 = Monday. Opens exactly at 11:00 (start inclusive).
    r = client.get("/api/restaurants/open?datetime=2026-05-04T11:00:00")
    assert "Beasley's Chicken + Honey" in r.json()


def test_beasleys_closed_at_noon_monday(client):
    # Half-open semantics: at 12:00 (close), already closed.
    r = client.get("/api/restaurants/open?datetime=2026-05-04T12:00:00")
    assert "Beasley's Chicken + Honey" not in r.json()


def test_beasleys_closed_at_8pm_monday(client):
    # Mon-Sat run only goes to noon, so 20:00 on Monday must be closed.
    r = client.get("/api/restaurants/open?datetime=2026-05-04T20:00:00")
    assert "Beasley's Chicken + Honey" not in r.json()


def test_beasleys_open_at_8pm_sunday(client):
    # 2026-05-10 = Sunday. Sunday segment is 11 am - 10 pm.
    r = client.get("/api/restaurants/open?datetime=2026-05-10T20:00:00")
    assert "Beasley's Chicken + Honey" in r.json()


# 42nd Street Oyster Bar: "Mon-Sat 11 am - 12 am  / Sun 12 pm - 2 am"
# Sunday's segment closes at Monday 02:00 — Sunday-to-Monday wraparound.

def test_42nd_street_open_monday_1am_via_sunday_wraparound(client):
    # 2026-05-04 = Monday. 01:00 is inside Sunday's wrap interval.
    r = client.get("/api/restaurants/open?datetime=2026-05-04T01:00:00")
    assert "42nd Street Oyster Bar" in r.json()


def test_42nd_street_closed_monday_2am_boundary(client):
    # Exactly the close minute — half-open semantics → closed.
    r = client.get("/api/restaurants/open?datetime=2026-05-04T02:00:00")
    assert "42nd Street Oyster Bar" not in r.json()


def test_42nd_street_closed_sunday_11am(client):
    # Sunday opens at noon, not 11 am.
    r = client.get("/api/restaurants/open?datetime=2026-05-10T11:00:00")
    assert "42nd Street Oyster Bar" not in r.json()


# Seoul 116: "Mon-Sun 11 am - 4 am"
# Every day's interval wraps past midnight. Catches a query that fails to look
# back to the prior day's segment when the current minute is in the small hours.

def test_seoul116_open_tuesday_2am_from_monday_segment(client):
    # 2026-05-05 = Tuesday. 02:00 is covered by Monday's interval (Mon 11am - Tue 4am).
    r = client.get("/api/restaurants/open?datetime=2026-05-05T02:00:00")
    assert "Seoul 116" in r.json()


def test_seoul116_closed_tuesday_5am_between_segments(client):
    # 05:00 is past Monday's close (04:00) and before Tuesday's open (11:00).
    r = client.get("/api/restaurants/open?datetime=2026-05-05T05:00:00")
    assert "Seoul 116" not in r.json()


def test_seoul116_open_tuesday_11am(client):
    # Tuesday's own interval opens at 11:00.
    r = client.get("/api/restaurants/open?datetime=2026-05-05T11:00:00")
    assert "Seoul 116" in r.json()


# The Cheesecake Factory: "Mon-Thu 11 am - 11 pm  / Fri-Sat 11 am - 12:30 am  / Sun 10 am - 11 pm"
# Friday's interval ends at exactly 12:30 am Saturday — pins down the half-hour
# boundary semantics on a wrapped close.

def test_cheesecake_factory_open_saturday_midnight_via_friday(client):
    # 2026-05-09 = Saturday. 00:00 is inside Friday's interval (Fri 11am - Sat 00:30).
    r = client.get("/api/restaurants/open?datetime=2026-05-09T00:00:00")
    assert "The Cheesecake Factory" in r.json()


def test_cheesecake_factory_closed_at_12_30am_saturday_boundary(client):
    # Exactly the close minute — half-open → closed.
    r = client.get("/api/restaurants/open?datetime=2026-05-09T00:30:00")
    assert "The Cheesecake Factory" not in r.json()


def test_cheesecake_factory_closed_saturday_1am_between_segments(client):
    # 01:00 is past Friday's close (00:30) and before Saturday's own open (11:00).
    r = client.get("/api/restaurants/open?datetime=2026-05-09T01:00:00")
    assert "The Cheesecake Factory" not in r.json()
