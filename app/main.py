"""FastAPI app + startup loader.

The CSV is parsed exactly once, on app startup. Subsequent requests query
the in-memory list. To pick up CSV changes, restart the process.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api import router
from app.loader import build_restaurants, load_csv

CSV_PATH = Path(__file__).resolve().parent.parent / "restaurants.csv"


@asynccontextmanager
async def lifespan(app: FastAPI):
    rows = load_csv(str(CSV_PATH))
    app.state.restaurants = build_restaurants(rows)
    yield


app = FastAPI(
    title="Restaurant Hours API",
    description="Returns restaurants open at a given local datetime.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)
