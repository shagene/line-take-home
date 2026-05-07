# Restaurant Hours API

A small Python API that answers one question: given a local datetime, which restaurants are open? It reads a CSV of restaurant names paired with human-readable hours strings (e.g. `"Mon-Thu, Sun 11:30 am - 10 pm / Fri-Sat 11:30 am - 11 pm"`), parses those strings once at startup into normalized weekly intervals, and serves a single endpoint that returns the list of restaurants open at the requested datetime. The technical core is the parser-plus-interval engine: messy human hours become integer week-minute ranges, and queries collapse to a single integer comparison.

The implementation is intentionally focused on the required endpoint. See [Design Decisions](#design-decisions) for the trade-off discussion.

## Quick Start

### With Docker

```bash
docker build -t restaurant-hours-api .
docker run -p 8000:8000 restaurant-hours-api
```

In another terminal:

```bash
curl "http://localhost:8000/api/restaurants/open?datetime=2026-05-06T10:45:00"
```

### Local Development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"

pytest
uvicorn app.main:app --reload
```

In another terminal:

```bash
curl "http://localhost:8000/api/restaurants/open?datetime=2026-05-06T10:45:00"
```

Python 3.12 is required.

## The Endpoint

### Request

| Method | Path | Query Parameter |
| ------ | ---- | --------------- |
| `GET`  | `/api/restaurants/open` | `datetime` (ISO 8601 local datetime, required) |

Example:

```text
GET /api/restaurants/open?datetime=2026-05-06T10:45:00
```

### Response

`200 OK` with a JSON list of restaurant names:

```json
[
  "Dashi",
  "Mez Mexican",
  "Tupelo Honey"
]
```

(Wednesday 10:45 AM — three restaurants serve breakfast or open early enough to be open at this hour.)

### Errors

- `422` if `datetime` is missing or cannot be parsed
- `200` with `[]` if no restaurants match the query (an empty list is not an error)

### Datetime Format

The `datetime` query parameter is an ISO 8601 local datetime with no timezone offset, for example `2026-05-06T10:45:00`. Pydantic handles parsing and validation automatically; malformed input produces a `422` response with field-level error details.

Interactive OpenAPI documentation is available at `/docs` (Swagger UI) and `/redoc` once the server is running.

## Algorithm

### Parse once, query simply

The API does not parse raw hours strings on every request. The CSV is loaded at startup, each restaurant's hours are parsed into a list of normalized intervals, and queries operate against the structured data. Parsing is the expensive, brittle step; doing it once turns every subsequent request into a fast integer-range check.

For example, this row:

```
Bida Manda
Mon-Thu, Sun 11:30 am - 10 pm / Fri-Sat 11:30 am - 11 pm
```

normalizes into seven daily intervals:

```
Monday    11:30 -> 22:00
Tuesday   11:30 -> 22:00
Wednesday 11:30 -> 22:00
Thursday  11:30 -> 22:00
Friday    11:30 -> 23:00
Saturday  11:30 -> 23:00
Sunday    11:30 -> 22:00
```

### Week-minute encoding

Each interval is stored as a pair of integers measured in minutes from the start of the week, with Monday 00:00 as zero:

| Day start  | Week-minute |
| ---------- | ----------: |
| Monday     |       0     |
| Tuesday    |    1440     |
| Wednesday  |    2880     |
| Thursday   |    4320     |
| Friday     |    5760     |
| Saturday   |    7200     |
| Sunday     |    8640     |
| End of Sun |   10080     |

The full week fits in `[0, 10080)`, which means every value comfortably fits in 14 bits and integer comparison is the only arithmetic the query path needs.

### Query

A request comes in, the local datetime is converted to a single week-minute, and the engine returns every restaurant with at least one matching interval:

```
query_minute = (weekday * 1440) + (hour * 60) + minute

for each interval (name, start, end):
    if start <= query_minute < end:
        include name in result
```

That `start <= query_minute < end` is the entire runtime check.

### Half-open intervals

Intervals are half-open: `[start, end)`. A restaurant is open exactly at its opening minute and closed exactly at its closing minute.

For `Mon 11 am - 10 pm`:

| Local time      | Status |
| --------------- | ------ |
| Monday 10:59 am | closed |
| Monday 11:00 am | open   |
| Monday 9:59 pm  | open   |
| Monday 10:00 pm | closed |

This removes ambiguity at boundaries and makes tests precise.

## Edge Cases

The parser and interval engine handle each of the following correctly. Every case has explicit test coverage.

- **Omitted days are closed.** `Centro: Mon, Wed-Sun ...` produces no Tuesday interval, so a Tuesday query for Centro returns nothing.
- **Half-open boundary.** Open at the opening minute; closed at the closing minute.
- **Overnight hours.** `Bonchon: Mon-Wed 5 pm - 12:30 am` becomes Monday 17:00 to Tuesday 00:30, so a Tuesday 12:15 AM query finds Bonchon open via Monday's interval.
- **All-week overnight.** `Seoul 116: Mon-Sun 11 am - 4 am` produces seven intervals that each spill into the next day, so Tuesday 2 AM is open via Monday's interval.
- **Sunday-to-Monday wraparound.** `Sun 8 pm - 2 am` cannot exceed week-minute 10080, so it splits into two intervals: Sunday 20:00 to end-of-week, and Monday 00:00 to Monday 02:00.
- **12 AM and 12 PM.** Converted to 00:00 and 12:00 respectively.
- **Closing time of `12 am`.** Treated as next-day midnight (24:00 within the day, not 0:00 of the same day).
- **Circular day ranges.** `Fri-Mon` expands forward through the week to Fri/Sat/Sun/Mon.
- **Comma-separated day groups.** `Mon-Thu, Sun` includes both segments; the parser handles arbitrary lists of ranges and singletons.

### Overnight Example

A live query against the included CSV that exercises overnight intervals:

```text
GET /api/restaurants/open?datetime=2026-05-10T01:00:00
```

```json
[
  "Bonchon",
  "Seoul 116"
]
```

Both restaurants are open at Sunday 1 AM because their Saturday hours extend into Sunday morning (`Bonchon: Sat 3 pm - 1:30 am` and `Seoul 116: Mon-Sun 11 am - 4 am`). Sunday's own hours haven't started yet (Bonchon opens at 3 PM, Seoul 116 at 11 AM).

## Repository Structure

```text
app/
  main.py        # FastAPI app factory and startup hook
  loader.py      # CSV reader, returns restaurant rows
  parser.py      # Hours-string grammar: days, times, segments
  intervals.py   # Week-minute encoding and query engine
  api.py         # Route definitions and Pydantic models

tests/
  test_parser_times.py     # 11 am, 12 am, 12:30 am, 12 pm
  test_parser_days.py      # Mon-Fri, Mon-Sun, Tues-Fri, Sun
  test_parser_segments.py  # Multi-segment "/" splits
  test_intervals.py        # Week-minute math, half-open semantics
  test_api.py              # End-to-end through the FastAPI client
  test_edge_cases.py       # Every case from the Edge Cases section

restaurants.csv  # Provided dataset, loaded at startup
README.md
Dockerfile
pyproject.toml
```

## Testing

### Test Categories

- **Parser unit tests** cover time formats, day expressions, and multi-segment schedule strings in isolation.
- **Interval engine tests** verify week-minute conversion and half-open `[start, end)` semantics independent of the parser.
- **API integration tests** exercise the live FastAPI app and are named after user behaviors: `test_open_now_evening`, `test_late_night_overnight_friday`, `test_sunday_brunch`, `test_invalid_datetime_returns_422`, and so on.
- **Edge case tests** map one-to-one onto the bullets in [Edge Cases](#edge-cases). Each case has at least one assertion.
- **Property-based tests** use Hypothesis to generate random valid intervals and verify invariants: a query at exactly `start` is open, a query at exactly `end` is closed, every minute inside a contiguous run produces the same answer, and so on.

### Running Tests

```bash
pytest
pytest --cov=app
```

Behavior-named integration tests double as living documentation. Reading the test names tells you what the API promises and who it is for, without having to read implementation code.

## Design Decisions

- **No SQL database.** The CSV is static input. Parsing into memory at startup is correct for static data; SQL would solve a problem this assignment doesn't have.
- **No CSV upload endpoint.** The CSV is the program's static input, not a runtime concern. Adding upload now would invent infrastructure the spec doesn't ask for.
- **No frontend.** The API is the deliverable. A frontend would not exercise the API in any way the tests don't already.
- **In-memory week-minute encoding.** Collapses the open/closed check to one integer comparison. The whole week fits in `[0, 10080)`.
- **Half-open `[start, end)` intervals.** Open at the opening minute, closed at the closing minute. Documented and tested explicitly so reviewers know which side of midnight wins.
- **FastAPI.** Built-in request validation via Pydantic, free OpenAPI docs at `/docs`, and modern test ergonomics with `httpx.TestClient`.

## Future Expansion

The current implementation is intentionally narrow. If this became a managed product with an admin upload workflow, the natural additions would be:

- SQL-backed storage with versioned imports
- `POST /api/imports` upload endpoint with transactional activation (parse and validate before swapping the active dataset)
- Admin UI for upload, parsed-hours preview, and import history
- Customer-facing UI with Live Mode and Simulated Time Mode for planning and demos
- Richer API response with `next_change_at` for efficient frontend refresh
- Optional Server-Sent Events for dataset version notifications

These are described in `approach-recommended.md` and would extend the existing parser and query algorithm without changing them.

## License / Attribution

This project is a take-home submission for Liine. Built by Steven Hagene.
