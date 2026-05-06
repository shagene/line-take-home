"""HTTP route handler for /api/restaurants/open."""

from datetime import datetime

from fastapi import APIRouter, Query, Request

from app.intervals import datetime_to_week_minute, find_open

router = APIRouter()


@router.get("/api/restaurants/open", response_model=list[str])
def get_open_restaurants(
    request: Request,
    datetime: datetime = Query(  # noqa: A002 — match the brief's parameter name
        ...,
        description="ISO 8601 local datetime, e.g. 2026-05-06T21:30:00",
    ),
) -> list[str]:
    """Return names of restaurants open at the given local datetime."""
    q = datetime_to_week_minute(datetime)
    return find_open(request.app.state.restaurants, q)
