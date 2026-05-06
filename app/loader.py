"""Load the restaurants CSV and build Restaurant objects with parsed intervals."""

import csv

from app.intervals import Restaurant
from app.parser import parse_hours


def load_csv(path: str) -> list[tuple[str, str]]:
    """Read the CSV at `path`. Returns [(name, raw_hours), ...] from the first two columns.

    Assumes a header row labeled exactly "Restaurant Name" and "Hours" (per the
    take-home brief: 'The CSV file will be well-formed').
    """
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        return [(row[0], row[1]) for row in reader if row]


def build_restaurants(rows: list[tuple[str, str]]) -> list[Restaurant]:
    """Convert (name, raw_hours) tuples into Restaurant objects with parsed intervals."""
    return [
        Restaurant(name=name, raw_hours=raw_hours, intervals=parse_hours(raw_hours))
        for name, raw_hours in rows
    ]
