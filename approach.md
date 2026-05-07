# Restaurant Hours API - Recommended Approach

## Summary

This project implements a small API for answering one question:

> Given a local datetime, which restaurants are open?

The assignment provides a CSV of restaurant names and human-readable hours. The API accepts a datetime string and returns the names of restaurants open at that date and time.

The core challenge is not the endpoint itself. The hard part is converting inconsistent human-readable hours into a reliable structure that can be queried correctly, especially around day ranges, multiple schedule segments, midnight, and overnight hours.

My approach is to keep the runtime API simple by doing the hard work once:

```text
CSV rows
-> parse human-readable hours
-> normalize into weekly open intervals
-> query intervals with integer comparison
-> return matching restaurant names
```

The implementation stays focused on the required API, but the design leaves a clear path toward a fuller restaurant-hours management product.

---

## Core Requirement

Required endpoint:

```text
GET /api/restaurants/open?datetime=2026-05-06T10:45:00
```

Required response shape (Wednesday 10:45 AM against the supplied CSV):

```json
[
  "Dashi",
  "Mez Mexican",
  "Tupelo Honey"
]
```

The endpoint returns a sorted list of restaurant names. If no restaurants are open, it returns an empty list.

The assignment assumptions are preserved:

```text
- If a day is not listed, the restaurant is closed on that day.
- All times are local.
- Timezone handling is out of scope.
- The CSV is well-formed.
- Restaurant names and hour strings are assumed to be correct.
```

---

## Design Principle

The main design decision is:

> Parse once, query simply.

The API should not parse raw strings on every request. Instead, the CSV is loaded when the app starts, each restaurant's hours are parsed into normalized intervals, and queries operate against that structured data.

Example:

```text
Bida Manda
Mon-Thu, Sun 11:30 am - 10 pm / Fri-Sat 11:30 am - 11 pm
```

Normalizes into:

```text
Monday    11:30 -> 22:00
Tuesday   11:30 -> 22:00
Wednesday 11:30 -> 22:00
Thursday  11:30 -> 22:00
Friday    11:30 -> 23:00
Saturday  11:30 -> 23:00
Sunday    11:30 -> 22:00
```

Once normalized, checking whether a restaurant is open becomes a simple interval comparison.

---

## Data Representation

I would represent each opening window as minutes from the start of the week.

Using Monday as the start:

```text
Monday 00:00 = 0
Tuesday 00:00 = 1440
Wednesday 00:00 = 2880
Sunday 23:59 = 10079
```

Each interval stores:

```text
restaurant_name
start_week_minute
end_week_minute
source_hours_segment
```

Intervals use half-open semantics:

```text
[start, end)
```

That means:

```text
Open exactly at opening time.
Closed exactly at closing time.
```

For example:

```text
Mon 11 am - 10 pm
```

Behavior:

```text
Monday 10:59 am = closed
Monday 11:00 am = open
Monday 9:59 pm = open
Monday 10:00 pm = closed
```

This avoids ambiguity at boundaries and makes tests precise.

For week-minute bounds, `start_week_minute` is in `[0, 10080)` and `end_week_minute` is in `(0, 10080]`. The value `10080` is only used as an exclusive end boundary for intervals that run through the end of Sunday.

---

## Overnight Hours

Overnight hours are handled by letting the closing time fall on the next day.

Example:

```text
Bonchon
Mon-Wed 5 pm - 12:30 am
```

Monday becomes:

```text
Monday 17:00 -> Tuesday 00:30
```

In week-minute form:

```text
1020 -> 1470
```

The query engine does not need special overnight logic. It only checks:

```text
start_week_minute <= query_week_minute < end_week_minute
```

For Sunday-to-Monday wraparound, the interval is split:

```text
Sun 8 pm - 2 am
```

Becomes:

```text
Sunday 20:00 -> end of week
Monday 00:00 -> Monday 02:00
```

This keeps every stored interval queryable with the same comparison.

---

## Parser Scope

The parser should support the formats present in the CSV and a reasonable grammar beyond the examples.

Supported day formats:

```text
Mon
Tue / Tues
Wed
Thu / Thurs
Fri
Sat
Sun
Monday through Sunday
```

Supported day expressions:

```text
Mon-Sun
Mon-Fri
Fri-Sat
Sat-Sun
Mon-Thu, Sun
Mon, Wed-Sun
Tues-Fri, Sun
```

Supported time formats:

```text
11 am
11:00 am
11:30 am
10 pm
10:30 pm
12 am
12 pm
12:30 am
1:30 am
```

The parser should be strict enough to be predictable, but flexible enough to handle common restaurant-hour variations.

---

## API Design

Primary endpoint:

```text
GET /api/restaurants/open?datetime=2026-05-06T10:45:00
```

Response (Wednesday 10:45 AM):

```json
[
  "Dashi",
  "Mez Mexican",
  "Tupelo Honey"
]
```

Error behavior:

```text
Missing datetime -> 422
Invalid datetime -> 422
Timezone-aware datetime -> 422  (the contract is local time only)
Date-only string (no T) -> 422
No restaurants open -> 200 with []
```

The API should preserve the assignment's requested response shape. A richer response could be added later, but the core endpoint should stay literal and easy to grade.

---

## Architecture

For this assessment, I would keep the implementation intentionally small:

```text
FastAPI app
CSV loader
hours parser
interval query engine
tests
Dockerfile
README
```

Suggested structure:

```text
app/
  main.py
  loader.py
  parser.py
  intervals.py
  api.py

tests/
  test_parser_times.py
  test_parser_days.py
  test_parser_segments.py
  test_intervals.py
  test_api.py
  test_edge_cases.py

restaurants.csv
README.md
Dockerfile
```

I would not start with SQL for this assignment. The CSV is static, small, and provided as input. Loading into memory at startup is simpler, easier to review, and fully satisfies the requirement.

If this became a managed product with uploads, dataset versioning, or multiple tenants, then SQL would become appropriate.

---

## User Personas

Six users shape the design. Each one maps to specific decisions elsewhere in this document and to a block of tests in `tests/test_personas.py`.

- **Marcus — hungry customer.** Wants to know what's open *right now*. Justifies the minimal query shape (`GET /api/restaurants/open?datetime=...`) and the choice to return just a list of names rather than full schedules. He never asks "what hours does this place keep" — only "is it open."
- **Priya — late-night planner.** Asks "what's open at 1 a.m. on Saturday?" She is why the parser and engine treat overnight intervals and Sunday-to-Monday wraparound as first-class cases, why the week-minute encoding splits week-crossing intervals at the boundary, and why `[start, end)` half-open semantics are explicit and tested rather than left implicit.
- **Leo — frontend developer.** Will build a UI on top of the API. He is why the response contract is rigid: a sorted JSON array of strings, `200 []` for no matches (never `404`), `422` with field-level errors for malformed input, and stable behavior at boundaries so the UI doesn't flicker around opening minutes.
- **Hannah — weekend dinner-only.** Plans Saturday lunch and discovers Garland (`Sat 5:30 pm - 11 pm`), David's Dumpling (`Sun 5:30 pm - 10 pm`), and Top of the Hill (`Sat 5 pm - 9 pm`) open only for dinner on those weekend days. She is why per-day asymmetry inside a multi-segment schedule must resolve exactly: a query at Sat 12:30 pm has to exclude Garland while keeping Mami Nora's (`Sat 11 am - 10 pm`) open. Sloppy day-grouping silently breaks her.
- **Aiden — weekend early-bird.** Wants breakfast at Sat 8 am. Char Grill (`Sat-Sun 7 am - 3 pm`), Mez Mexican (`Sat-Sun 10 am - 9:30 pm`), and Dashi (`Sat-Sun 9:30 am - 9:30 pm`) open earlier on weekends than weekdays — sometimes only on weekends. He proves multi-segment schedules with weekend-specific open times resolve correctly.
- **Dana — Tuesday-night planner.** Centro (`Mon, Wed-Sun 11 am - 10 pm`) is closed Tuesdays. Dana's query at Tue 7 pm has to exclude Centro while keeping its Wednesday-open neighbors. She makes "comma-then-range with a skipped day" a behavioral test rather than a parser-internal one.

Every behavioral test traces back to one of these users. If a feature can't be motivated by one of them, it's out of scope for this submission.

---

## Testing Strategy

The test suite is the most important part of the submission after the parser.

I would test:

```text
Time parsing:
- 11 am
- 11:30 am
- 12 am
- 12 pm
- 12:30 am

Day parsing:
- Mon-Fri
- Mon-Sun
- Mon-Thu, Sun
- Mon, Wed-Sun
- Tues-Fri, Sun

Boundary behavior:
- open exactly at opening time
- closed exactly at closing time

Overnight behavior:
- Monday evening into Tuesday morning
- all-week overnight hours like Seoul 116
- Sunday-to-Monday wraparound

CSV/API behavior:
- expected restaurants included
- expected restaurants excluded
- omitted days treated as closed
- invalid datetime returns validation error
- no matches returns empty list
```

The goal is not just high coverage. The goal is to prove correctness around the cases a naive implementation is likely to fail.

---

## Docker

The Dockerfile should allow the reviewer to run the app without local setup.

Expected flow:

```text
docker build -t restaurant-hours-api .
docker run -p 8000:8000 restaurant-hours-api
```

Then:

```text
GET http://localhost:8000/api/restaurants/open?datetime=2026-05-06T10:45:00
```

Docker is a useful bonus because the prompt explicitly calls it out.

---

## Product Expansion

The focused implementation solves the assignment, but the architecture points naturally toward a fuller product.

If this became a production restaurant-hours platform, I would add:

```text
- SQL-backed storage
- CSV upload endpoint
- import history
- transactional dataset activation
- admin preview of parsed hours
- richer API response with open-until times
- next_change_at for efficient frontend refreshes
- customer-facing date/time search UI
- simulated time mode for planning and demos
```

The production version would separate ingestion from querying:

```text
Admin upload
-> parse and validate CSV
-> store raw rows and normalized intervals
-> activate dataset only after successful import
-> customer API queries active intervals
```

That is the scalable version. For the take-home, I would document this path without building all of it.

---

## Final Positioning

This submission is intentionally narrow in implementation and broad in design awareness.

The delivered app focuses on:

```text
- correct parsing
- clean normalization
- simple API behavior
- edge-case tests
- easy local/Docker execution
```

The documentation explains how the same foundation could grow into a product with uploads, persistence, admin workflows, and frontend time exploration.

The goal is to show both sides:

```text
I can solve the exact problem cleanly.
I can also see the product this could become.
```
