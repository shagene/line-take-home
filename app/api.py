"""HTTP route handler for /api/restaurants/open."""

from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import BeforeValidator, NaiveDatetime

from app.intervals import datetime_to_week_minute, find_open

router = APIRouter()


def _require_t_separator(value):
    """Require an explicit time component (rejects date-only and space-separated forms)."""
    if isinstance(value, str) and "T" not in value:
        raise ValueError(
            "datetime must use ISO 8601 with a 'T' separator, e.g. 2026-05-06T10:45:00"
        )
    return value


@router.get("/api/restaurants/open", response_model=list[str])
def get_open_restaurants(
    request: Request,
    query_datetime: Annotated[
        NaiveDatetime,
        BeforeValidator(_require_t_separator),
        Query(
            alias="datetime",
            description=(
                "ISO 8601 local datetime with a 'T' separator and no timezone offset, "
                "e.g. 2026-05-06T10:45:00. Date-only strings and timezone-aware values "
                "(Z or +HH:MM) are rejected with 422."
            ),
        ),
    ],
) -> list[str]:
    """Return names of restaurants open at the given local datetime."""
    q = datetime_to_week_minute(query_datetime)
    return find_open(request.app.state.restaurants, q)
