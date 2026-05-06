# Restaurant Hours API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python API that takes a datetime string and returns the names of restaurants open at that date and time, parsed from a static CSV of human-readable hours.

**Architecture:** Parse hours once at startup into in-memory week-minute integer intervals. The runtime query is a single integer-range comparison (`start <= q < end`) over a list. No database, no CSV upload, no frontend.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, uvicorn, pytest, pytest-cov, Hypothesis, Docker.

**Spec:** See `/Users/stevenhagene/Projects/liine/approach-recommended.md` for the design rationale.

---

## File Structure

The repo is intentionally flat. Each module has one job.

```text
restaurant-hours-api/
  README.md                # User-facing docs (drafted in parallel)
  Dockerfile               # Single-stage container
  pyproject.toml           # Python project config + deps
  restaurants.csv          # Static data fixture (already exists)

  app/
    __init__.py            # empty
    main.py                # FastAPI app + lifespan loader
    api.py                 # Route handler for /api/restaurants/open
    loader.py              # CSV reading + Restaurant construction
    parser.py              # Hours-string parsing
    intervals.py           # Types + week-minute helpers + query

  tests/
    __init__.py            # empty
    conftest.py            # Shared pytest fixtures
    test_parser_times.py
    test_parser_days.py
    test_parser_segments.py
    test_intervals.py
    test_loader.py
    test_api.py
    test_personas.py       # Tests named after user behaviors
    test_edge_cases.py
    test_property_based.py # Hypothesis-driven tests
```

---

## Type Contracts (defined in Task 7, referenced throughout)

These types are introduced in Task 7 (`app/intervals.py`) and used by every module that follows. The plan's later tasks assume these exact signatures.

```python
# app/intervals.py
from dataclasses import dataclass
from datetime import datetime

WEEK_MINUTES = 10080  # 7 * 24 * 60


@dataclass(frozen=True)
class Interval:
    start_week_minute: int    # 0..10079
    end_week_minute: int      # 1..10080 (exclusive)
    source_segment: str       # the schedule segment this came from


@dataclass
class Restaurant:
    name: str
    raw_hours: str
    intervals: list[Interval]


def to_week_minute(day_index: int, minute_of_day: int) -> int: ...
def datetime_to_week_minute(dt: datetime) -> int: ...
def find_open(restaurants: list[Restaurant], q: int) -> list[str]: ...
```

```python
# app/parser.py
from app.intervals import Interval

def parse_time(s: str) -> int: ...                                     # → 0..1439
def expand_days(s: str) -> list[int]:                                  # → list of 0..6
def split_segments(s: str) -> list[str]: ...
def parse_segment(s: str) -> tuple[list[int], int, int]: ...           # → (days, open, close)
def build_intervals(
    day_indices: list[int], open_time: int, close_time: int, source: str
) -> list[Interval]: ...
def parse_hours(s: str) -> list[Interval]: ...                         # top-level
```

```python
# app/loader.py
from app.intervals import Restaurant

def load_csv(path: str) -> list[tuple[str, str]]: ...                  # → [(name, raw_hours)]
def build_restaurants(rows: list[tuple[str, str]]) -> list[Restaurant]: ...
```

---

## Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `.gitignore`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "restaurant-hours-api"
version = "0.1.0"
description = "API that returns restaurants open at a given datetime."
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "pydantic>=2.6",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.1",
    "httpx>=0.27",
    "hypothesis>=6.100",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["app*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v"
```

- [ ] **Step 2: Create empty package files**

```python
# app/__init__.py
```

```python
# tests/__init__.py
```

- [ ] **Step 3: Create stub `app/main.py`**

```python
from fastapi import FastAPI

app = FastAPI(title="Restaurant Hours API")
```

- [ ] **Step 4: Create stub `tests/conftest.py`**

```python
"""Shared pytest fixtures for the restaurant-hours-api test suite."""
```

- [ ] **Step 5: Create `.gitignore`**

```text
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.coverage
htmlcov/
.venv/
venv/
.env
```

- [ ] **Step 6: Install dependencies**

Run: `pip install -e ".[dev]"`
Expected: installs FastAPI, pytest, hypothesis, etc. without errors.

- [ ] **Step 7: Verify the app starts and pytest runs**

Run: `python -c "from app.main import app; print(app.title)"`
Expected: `Restaurant Hours API`

Run: `pytest`
Expected: `no tests ran in 0.0Xs` (exit code 5 is acceptable; no tests yet).

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml app tests .gitignore
git commit -m "chore: project scaffold with FastAPI app and pytest config"
```

---

## Task 2: Time parser - simple cases

Parse hour-only times like `"11 am"` and `"10 pm"` into minutes-after-midnight.

**Files:**
- Create: `app/parser.py`
- Create: `tests/test_parser_times.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_parser_times.py
import pytest

from app.parser import parse_time


@pytest.mark.parametrize("input_str, expected", [
    ("11 am", 660),
    ("10 pm", 1320),
    ("1 am", 60),
    ("9 pm", 21 * 60),
])
def test_parse_time_simple_hours(input_str, expected):
    assert parse_time(input_str) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_parser_times.py -v`
Expected: `ImportError` or `ModuleNotFoundError` for `app.parser`.

- [ ] **Step 3: Write minimal implementation**

```python
# app/parser.py
import re

_TIME_PATTERN = re.compile(
    r"^\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s*$",
    flags=re.IGNORECASE,
)


def parse_time(s: str) -> int:
    """Parse '11 am', '11:30 pm', '12 am', '12 pm' → minutes after midnight (0..1439)."""
    match = _TIME_PATTERN.match(s)
    if not match:
        raise ValueError(f"unrecognized time: {s!r}")
    hour = int(match.group(1))
    minute = int(match.group(2)) if match.group(2) else 0
    suffix = match.group(3).lower()
    if suffix == "am":
        if hour == 12:
            hour = 0
    else:  # pm
        if hour != 12:
            hour += 12
    return hour * 60 + minute
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_parser_times.py -v`
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/parser.py tests/test_parser_times.py
git commit -m "feat: parse simple am/pm times to minutes-of-day"
```

---

## Task 3: Time parser - minutes and edge cases

Cover times with explicit minutes (`"11:30 am"`, `"1:30 am"`) and the 12am/12pm conversions which are the most common parser bug.

**Files:**
- Modify: `tests/test_parser_times.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_parser_times.py`:

```python
@pytest.mark.parametrize("input_str, expected", [
    ("11:30 am", 690),
    ("11:00 am", 660),
    ("10:30 pm", 22 * 60 + 30),
    ("1:30 am", 90),
    ("12:30 pm", 12 * 60 + 30),
])
def test_parse_time_with_minutes(input_str, expected):
    assert parse_time(input_str) == expected


@pytest.mark.parametrize("input_str, expected", [
    ("12 am", 0),
    ("12 pm", 720),
    ("12:00 am", 0),
    ("12:00 pm", 720),
    ("12:30 am", 30),
    ("12:30 pm", 750),
])
def test_parse_time_handles_12_am_and_12_pm(input_str, expected):
    assert parse_time(input_str) == expected


def test_parse_time_rejects_garbage():
    with pytest.raises(ValueError):
        parse_time("not a time")
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_parser_times.py -v`
Expected: All tests pass — the implementation from Task 2 already handles minutes and 12am/12pm correctly via the regex and the `if hour == 12` branches. If any fail, the implementation must be fixed before continuing.

- [ ] **Step 3: Commit**

```bash
git add tests/test_parser_times.py
git commit -m "test: cover time parser minutes and 12am/12pm edge cases"
```

---

## Task 4: Day parser - tokens and ranges

Parse single day tokens (`"Mon"`, `"Tues"`, `"Monday"`) and simple ranges (`"Mon-Fri"`).

**Files:**
- Modify: `app/parser.py`
- Create: `tests/test_parser_days.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_parser_days.py
import pytest

from app.parser import expand_days


@pytest.mark.parametrize("input_str, expected", [
    ("Mon", [0]),
    ("Tue", [1]),
    ("Tues", [1]),
    ("Wed", [2]),
    ("Thu", [3]),
    ("Thurs", [3]),
    ("Fri", [4]),
    ("Sat", [5]),
    ("Sun", [6]),
    ("Monday", [0]),
    ("Sunday", [6]),
])
def test_expand_days_single_tokens(input_str, expected):
    assert expand_days(input_str) == expected


@pytest.mark.parametrize("input_str, expected", [
    ("Mon-Fri", [0, 1, 2, 3, 4]),
    ("Sat-Sun", [5, 6]),
    ("Mon-Sun", [0, 1, 2, 3, 4, 5, 6]),
    ("Tues-Thurs", [1, 2, 3]),
])
def test_expand_days_simple_ranges(input_str, expected):
    assert expand_days(input_str) == expected


def test_expand_days_rejects_unknown_token():
    with pytest.raises(ValueError):
        expand_days("Funday")
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_parser_days.py -v`
Expected: ImportError for `expand_days`.

- [ ] **Step 3: Implement `expand_days` for tokens and simple ranges**

Add to `app/parser.py`:

```python
_DAY_LOOKUP: dict[str, int] = {
    "mon": 0, "monday": 0,
    "tue": 1, "tues": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thurs": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}


def _day_index(token: str) -> int:
    key = token.strip().lower()
    if key not in _DAY_LOOKUP:
        raise ValueError(f"unrecognized day token: {token!r}")
    return _DAY_LOOKUP[key]


def _expand_range(start: int, end: int) -> list[int]:
    """Expand a day-index range (inclusive). Wraps if start > end (e.g. Fri-Mon)."""
    days: list[int] = []
    i = start
    while True:
        days.append(i)
        if i == end:
            break
        i = (i + 1) % 7
    return days


def expand_days(s: str) -> list[int]:
    """Parse 'Mon', 'Mon-Fri', 'Mon-Thu, Sun', 'Fri-Mon' → list of 0..6 day indices.

    Comma-separated groups are expanded and concatenated in input order.
    Ranges support wraparound (Fri-Mon → 4, 5, 6, 0).
    Duplicates are not removed; the parser produces a clean list because
    real CSVs don't repeat days within one expression.
    """
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if not parts:
        raise ValueError(f"empty day expression: {s!r}")
    result: list[int] = []
    for part in parts:
        if "-" in part:
            start_token, end_token = part.split("-", 1)
            result.extend(_expand_range(_day_index(start_token), _day_index(end_token)))
        else:
            result.append(_day_index(part))
    return result
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_parser_days.py -v`
Expected: all parametrized cases pass.

- [ ] **Step 5: Commit**

```bash
git add app/parser.py tests/test_parser_days.py
git commit -m "feat: parse day tokens and simple day ranges"
```

---

## Task 5: Day parser - circular ranges and comma groups

Cover wraparound ranges like `"Fri-Mon"` and comma-separated groups like `"Mon-Thu, Sun"`.

**Files:**
- Modify: `tests/test_parser_days.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_parser_days.py`:

```python
@pytest.mark.parametrize("input_str, expected", [
    ("Fri-Mon", [4, 5, 6, 0]),
    ("Sat-Tue", [5, 6, 0, 1]),
    ("Sun-Mon", [6, 0]),
])
def test_expand_days_circular_ranges(input_str, expected):
    assert expand_days(input_str) == expected


@pytest.mark.parametrize("input_str, expected", [
    ("Mon, Wed-Sun", [0, 2, 3, 4, 5, 6]),
    ("Mon-Thu, Sun", [0, 1, 2, 3, 6]),
    ("Tues-Fri, Sun", [1, 2, 3, 4, 6]),
    ("Mon, Wed, Fri", [0, 2, 4]),
])
def test_expand_days_comma_groups(input_str, expected):
    assert expand_days(input_str) == expected
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_parser_days.py -v`
Expected: all pass — the `_expand_range` helper from Task 4 already handles wraparound, and `expand_days` already handles commas. If anything fails the implementation must be revisited.

- [ ] **Step 3: Commit**

```bash
git add tests/test_parser_days.py
git commit -m "test: cover circular day ranges and comma-separated day groups"
```

---

## Task 6: Schedule segment splitting

Split a full hours string by `/` into independent schedule segments.

**Files:**
- Modify: `app/parser.py`
- Create: `tests/test_parser_segments.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_parser_segments.py
import pytest

from app.parser import split_segments


def test_split_segments_single_returns_one():
    assert split_segments("Mon-Sun 11 am - 10 pm") == ["Mon-Sun 11 am - 10 pm"]


def test_split_segments_two_segments():
    raw = "Mon-Thu 11 am - 10 pm / Fri-Sat 11 am - 12 am"
    assert split_segments(raw) == [
        "Mon-Thu 11 am - 10 pm",
        "Fri-Sat 11 am - 12 am",
    ]


def test_split_segments_three_segments():
    raw = "Mon-Thu 11 am - 11 pm / Fri-Sat 11 am - 12:30 am / Sun 10 am - 11 pm"
    assert split_segments(raw) == [
        "Mon-Thu 11 am - 11 pm",
        "Fri-Sat 11 am - 12:30 am",
        "Sun 10 am - 11 pm",
    ]


def test_split_segments_tolerates_extra_whitespace():
    raw = "Mon-Thu 11 am - 10 pm  /  Fri-Sat 11 am - 12 am"
    assert split_segments(raw) == [
        "Mon-Thu 11 am - 10 pm",
        "Fri-Sat 11 am - 12 am",
    ]


def test_split_segments_rejects_empty_segment():
    with pytest.raises(ValueError):
        split_segments("Mon 11 am - 10 pm //  Tue 5 pm - 11 pm")
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_parser_segments.py -v`
Expected: ImportError for `split_segments`.

- [ ] **Step 3: Implement `split_segments`**

Add to `app/parser.py`:

```python
def split_segments(s: str) -> list[str]:
    """Split 'A / B / C' into ['A', 'B', 'C'], stripped of whitespace.

    A solitary string with no '/' returns a single-element list.
    Empty segments (caused by '//' or trailing slashes) raise ValueError.
    """
    parts = [p.strip() for p in s.split("/")]
    if any(p == "" for p in parts):
        raise ValueError(f"empty segment in hours string: {s!r}")
    return parts
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_parser_segments.py -v`
Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/parser.py tests/test_parser_segments.py
git commit -m "feat: split hours string by / into schedule segments"
```

---

## Task 7: Interval types and week-minute helpers

Introduce the `Interval` and `Restaurant` dataclasses and the week-minute conversion helpers. This is the foundation every later task uses.

**Files:**
- Create: `app/intervals.py`
- Create: `tests/test_intervals.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_intervals.py
from datetime import datetime

import pytest

from app.intervals import (
    Interval,
    Restaurant,
    WEEK_MINUTES,
    datetime_to_week_minute,
    find_open,
    to_week_minute,
)


def test_week_minutes_constant():
    assert WEEK_MINUTES == 7 * 24 * 60 == 10080


@pytest.mark.parametrize("day_index, minute_of_day, expected", [
    (0, 0, 0),
    (0, 660, 660),
    (1, 0, 1440),
    (2, 0, 2880),
    (6, 0, 8640),
    (6, 1439, 10079),
])
def test_to_week_minute(day_index, minute_of_day, expected):
    assert to_week_minute(day_index, minute_of_day) == expected


@pytest.mark.parametrize("dt, expected", [
    (datetime(2026, 5, 4, 0, 0), 0),       # Monday 00:00
    (datetime(2026, 5, 4, 11, 0), 660),    # Monday 11:00
    (datetime(2026, 5, 6, 21, 30), 4170),  # Wednesday 21:30
    (datetime(2026, 5, 10, 23, 59), 10079),  # Sunday 23:59
])
def test_datetime_to_week_minute(dt, expected):
    assert datetime_to_week_minute(dt) == expected


def _make_restaurant(name: str, intervals: list[tuple[int, int]]) -> Restaurant:
    return Restaurant(
        name=name,
        raw_hours="<test>",
        intervals=[Interval(s, e, "<test>") for s, e in intervals],
    )


def test_find_open_returns_sorted_names_for_matching_intervals():
    restaurants = [
        _make_restaurant("B", [(0, 1440)]),
        _make_restaurant("A", [(0, 1440)]),
        _make_restaurant("C", [(2000, 3000)]),
    ]
    assert find_open(restaurants, 600) == ["A", "B"]


def test_find_open_excludes_at_closing_minute():
    restaurants = [_make_restaurant("X", [(660, 1320)])]
    assert find_open(restaurants, 1320) == []


def test_find_open_includes_at_opening_minute():
    restaurants = [_make_restaurant("X", [(660, 1320)])]
    assert find_open(restaurants, 660) == ["X"]


def test_find_open_empty_when_no_match():
    restaurants = [_make_restaurant("X", [(0, 100)])]
    assert find_open(restaurants, 5000) == []
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_intervals.py -v`
Expected: ImportError for `app.intervals`.

- [ ] **Step 3: Implement `app/intervals.py`**

```python
"""Interval types and week-minute helpers.

The week is encoded as a single integer in [0, 10080):
  Monday 00:00 = 0
  Tuesday 00:00 = 1440
  ...
  Sunday 23:59 = 10079

This collapses the open/closed check to a single integer-range comparison.
Intervals are half-open [start, end).
"""

from dataclasses import dataclass
from datetime import datetime

WEEK_MINUTES = 10080  # 7 * 24 * 60


@dataclass(frozen=True)
class Interval:
    start_week_minute: int
    end_week_minute: int
    source_segment: str


@dataclass
class Restaurant:
    name: str
    raw_hours: str
    intervals: list[Interval]


def to_week_minute(day_index: int, minute_of_day: int) -> int:
    """Convert (day_index 0..6, minute_of_day 0..1439) → week-minute 0..10079."""
    return day_index * 1440 + minute_of_day


def datetime_to_week_minute(dt: datetime) -> int:
    """Convert a naive datetime to a query week-minute (Monday=0)."""
    return to_week_minute(dt.weekday(), dt.hour * 60 + dt.minute)


def find_open(restaurants: list[Restaurant], q: int) -> list[str]:
    """Return the sorted names of restaurants with any interval matching q.

    A restaurant matches if any of its intervals satisfies start <= q < end.
    """
    return sorted(
        r.name
        for r in restaurants
        if any(i.start_week_minute <= q < i.end_week_minute for i in r.intervals)
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_intervals.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/intervals.py tests/test_intervals.py
git commit -m "feat: add Interval/Restaurant types and week-minute helpers"
```

---

## Task 8: Parse a single schedule segment

Convert one segment like `"Mon-Fri 11 am - 10 pm"` into `(day_indices, open_time, close_time)`.

**Files:**
- Modify: `app/parser.py`
- Modify: `tests/test_parser_segments.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_parser_segments.py`:

```python
from app.parser import parse_segment


def test_parse_segment_simple_day():
    assert parse_segment("Mon 11 am - 10 pm") == ([0], 660, 1320)


def test_parse_segment_simple_range():
    assert parse_segment("Mon-Fri 11 am - 10 pm") == ([0, 1, 2, 3, 4], 660, 1320)


def test_parse_segment_comma_groups():
    assert parse_segment("Mon-Thu, Sun 11:30 am - 10 pm") == ([0, 1, 2, 3, 6], 690, 1320)


def test_parse_segment_overnight_close():
    # Closing time before opening — overnight (handled later in build_intervals).
    assert parse_segment("Mon 5 pm - 1:30 am") == ([0], 1020, 90)


def test_parse_segment_rejects_missing_dash():
    with pytest.raises(ValueError):
        parse_segment("Mon 11 am 10 pm")
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_parser_segments.py -v -k parse_segment`
Expected: ImportError or "name 'parse_segment' is not defined".

- [ ] **Step 3: Implement `parse_segment`**

Add to `app/parser.py`:

```python
_SEGMENT_TIME_PATTERN = re.compile(
    r"\d{1,2}(?::\d{2})?\s*(?:am|pm)",
    flags=re.IGNORECASE,
)


def parse_segment(s: str) -> tuple[list[int], int, int]:
    """Parse one schedule segment like 'Mon-Fri 11 am - 10 pm'.

    Returns (day_indices, open_time_minutes, close_time_minutes).
    Times are minutes-of-day (0..1439). Overnight handling (close <= open)
    happens later, in build_intervals.
    """
    times = _SEGMENT_TIME_PATTERN.findall(s)
    if len(times) != 2:
        raise ValueError(f"expected exactly two times in segment: {s!r}")
    open_str, close_str = times
    # Find where the time range starts so we can isolate the day expression.
    time_range_start = s.lower().find(open_str.lower())
    day_expr = s[:time_range_start].rstrip(" -")
    open_time = parse_time(open_str)
    close_time = parse_time(close_str)
    days = expand_days(day_expr)
    return days, open_time, close_time
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_parser_segments.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/parser.py tests/test_parser_segments.py
git commit -m "feat: parse a single schedule segment to (days, open, close)"
```

---

## Task 9: Build intervals - same-day

Convert one parsed segment into a list of `Interval` objects, one per day. Handle the simple non-overnight case first.

**Files:**
- Modify: `app/parser.py`
- Modify: `tests/test_parser_segments.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_parser_segments.py`:

```python
from app.intervals import Interval
from app.parser import build_intervals


def test_build_intervals_same_day_single():
    intervals = build_intervals([0], 660, 1320, "Mon 11 am - 10 pm")
    assert intervals == [Interval(660, 1320, "Mon 11 am - 10 pm")]


def test_build_intervals_same_day_multiple():
    intervals = build_intervals([0, 1, 2], 660, 1320, "Mon-Wed 11 am - 10 pm")
    assert intervals == [
        Interval(660, 1320, "Mon-Wed 11 am - 10 pm"),
        Interval(2100, 2760, "Mon-Wed 11 am - 10 pm"),
        Interval(3540, 4200, "Mon-Wed 11 am - 10 pm"),
    ]
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_parser_segments.py -v -k build_intervals`
Expected: NameError or ImportError for `build_intervals`.

- [ ] **Step 3: Implement same-day case in `build_intervals`**

Add to `app/parser.py`:

```python
from app.intervals import Interval, WEEK_MINUTES, to_week_minute


def build_intervals(
    day_indices: list[int],
    open_time: int,
    close_time: int,
    source: str,
) -> list[Interval]:
    """Build normalized week-minute intervals from a parsed segment.

    Same-day case: close > open. One Interval per day.
    Overnight case: close <= open. (Handled in Task 10.)
    Sunday wraparound case: overnight on Sunday spills past WEEK_MINUTES.
    (Handled in Task 11.)
    """
    intervals: list[Interval] = []
    for day in day_indices:
        if close_time > open_time:
            start = to_week_minute(day, open_time)
            end = to_week_minute(day, close_time)
            intervals.append(Interval(start, end, source))
        else:
            # Overnight or zero-length — implemented in Task 10.
            raise NotImplementedError("overnight handling added in Task 10")
    return intervals
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_parser_segments.py -v -k build_intervals`
Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/parser.py tests/test_parser_segments.py
git commit -m "feat: build same-day intervals from a parsed segment"
```

---

## Task 10: Build intervals - overnight

Handle overnight hours (closing time ≤ opening time means the closing time belongs to the next day).

**Files:**
- Modify: `app/parser.py`
- Modify: `tests/test_parser_segments.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_parser_segments.py`:

```python
def test_build_intervals_overnight_simple():
    # Mon 5 pm - 1:30 am → Monday 17:00 → Tuesday 01:30
    intervals = build_intervals([0], 1020, 90, "Mon 5 pm - 1:30 am")
    assert intervals == [Interval(1020, 1530, "Mon 5 pm - 1:30 am")]


def test_build_intervals_overnight_all_week():
    # Seoul 116 case: Mon-Sun 11 am - 4 am.
    intervals = build_intervals([0, 1, 2, 3, 4, 5], 660, 240, "Mon-Sat 11 am - 4 am")
    expected = [
        Interval(660, 1680, "Mon-Sat 11 am - 4 am"),     # Mon 11:00 → Tue 04:00
        Interval(2100, 3120, "Mon-Sat 11 am - 4 am"),    # Tue 11:00 → Wed 04:00
        Interval(3540, 4560, "Mon-Sat 11 am - 4 am"),    # Wed 11:00 → Thu 04:00
        Interval(4980, 6000, "Mon-Sat 11 am - 4 am"),    # Thu 11:00 → Fri 04:00
        Interval(6420, 7440, "Mon-Sat 11 am - 4 am"),    # Fri 11:00 → Sat 04:00
        Interval(7860, 8880, "Mon-Sat 11 am - 4 am"),    # Sat 11:00 → Sun 04:00
    ]
    assert intervals == expected
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_parser_segments.py -v -k overnight`
Expected: tests fail with `NotImplementedError`.

- [ ] **Step 3: Replace the `NotImplementedError` branch**

In `app/parser.py`, replace the body of `build_intervals` with:

```python
def build_intervals(
    day_indices: list[int],
    open_time: int,
    close_time: int,
    source: str,
) -> list[Interval]:
    """Build normalized week-minute intervals from a parsed segment.

    Same-day case: close > open. One Interval per day.
    Overnight case: close <= open. End time belongs to the next day, so the
    interval becomes [start, start + (1440 - open + close)).
    Sunday wraparound case is handled in Task 11.
    """
    intervals: list[Interval] = []
    for day in day_indices:
        start = to_week_minute(day, open_time)
        if close_time > open_time:
            end = to_week_minute(day, close_time)
        else:
            # Overnight: closing time is the next day. Compute end as
            # (next_day_start + close_time). Sunday wraparound is split
            # in Task 11; here end may exceed WEEK_MINUTES temporarily.
            end = to_week_minute(day + 1, close_time)
        intervals.append(Interval(start, end, source))
    return intervals
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_parser_segments.py -v -k "overnight or build_intervals"`
Expected: all build_intervals tests pass (same-day + overnight).

- [ ] **Step 5: Commit**

```bash
git add app/parser.py tests/test_parser_segments.py
git commit -m "feat: support overnight intervals in build_intervals"
```

---

## Task 11: Build intervals - Sunday-to-Monday wraparound

Handle the special case where Sunday's overnight close spills past `WEEK_MINUTES` (e.g., `Sun 8 pm - 2 am` ends Monday at 02:00). Split such intervals into two so every stored interval stays in `[0, 10080]`.

**Files:**
- Modify: `app/parser.py`
- Modify: `tests/test_parser_segments.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_parser_segments.py`:

```python
def test_build_intervals_sunday_wraparound():
    # Sun 8 pm - 2 am → splits into Sunday 20:00 → 10080 and Monday 00:00 → 02:00.
    intervals = build_intervals([6], 1200, 120, "Sun 8 pm - 2 am")
    assert intervals == [
        Interval(8640 + 1200, 10080, "Sun 8 pm - 2 am"),  # Sun 20:00 → end of week
        Interval(0, 120, "Sun 8 pm - 2 am"),               # Mon 00:00 → 02:00
    ]


def test_build_intervals_seoul_116_full_week():
    # Mon-Sun 11 am - 4 am: Sunday's overnight wraps to Monday.
    intervals = build_intervals([0, 1, 2, 3, 4, 5, 6], 660, 240, "Mon-Sun 11 am - 4 am")
    # Monday through Saturday: same as Task 10 expected (each is overnight to next day).
    # Sunday: Sun 11:00 → end of week, then Mon 00:00 → 04:00.
    assert Interval(8640 + 660, 10080, "Mon-Sun 11 am - 4 am") in intervals
    assert Interval(0, 240, "Mon-Sun 11 am - 4 am") in intervals
    assert len(intervals) == 8  # 6 normal + 2 from Sunday wraparound
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_parser_segments.py -v -k wraparound`
Expected: failing assertion — Sunday's overnight currently produces an interval where `end > WEEK_MINUTES`.

- [ ] **Step 3: Update `build_intervals` to split Sunday wraparound**

In `app/parser.py`, replace `build_intervals` with:

```python
def build_intervals(
    day_indices: list[int],
    open_time: int,
    close_time: int,
    source: str,
) -> list[Interval]:
    """Build normalized week-minute intervals from a parsed segment.

    Same-day:    close > open  → one Interval per day.
    Overnight:   close <= open → end belongs to the next day.
    Sunday wrap: overnight on Sunday is split into two Intervals so every
                 stored interval lies in [0, 10080].
    """
    intervals: list[Interval] = []
    for day in day_indices:
        start = to_week_minute(day, open_time)
        if close_time > open_time:
            intervals.append(Interval(start, to_week_minute(day, close_time), source))
            continue
        # Overnight: close belongs to next day.
        if day == 6:
            # Sunday → Monday wraparound. Split into two intervals.
            intervals.append(Interval(start, WEEK_MINUTES, source))
            if close_time > 0:
                intervals.append(Interval(0, close_time, source))
        else:
            intervals.append(Interval(start, to_week_minute(day + 1, close_time), source))
    return intervals
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_parser_segments.py -v`
Expected: all build_intervals tests pass, including the wraparound cases.

- [ ] **Step 5: Commit**

```bash
git add app/parser.py tests/test_parser_segments.py
git commit -m "feat: split Sunday-to-Monday overnight intervals at week boundary"
```

---

## Task 12: Top-level parse_hours

Tie the pieces together: `parse_hours("Mon-Thu 11 am - 10 pm / Fri-Sat 11 am - 12 am")` should return all the normalized intervals for one restaurant.

**Files:**
- Modify: `app/parser.py`
- Create: `tests/test_parser_full.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_parser_full.py
from app.intervals import Interval
from app.parser import parse_hours


def test_parse_hours_single_segment():
    intervals = parse_hours("Mon-Sun 11:00 am - 10 pm")
    assert len(intervals) == 7
    assert all(i.start_week_minute % 1440 == 660 for i in intervals)
    assert all((i.end_week_minute - 1) % 1440 == 22 * 60 - 1 for i in intervals)


def test_parse_hours_multiple_segments():
    intervals = parse_hours(
        "Mon-Thu, Sun 11:30 am - 10 pm / Fri-Sat 11:30 am - 11 pm"
    )
    days_seen = sorted({i.start_week_minute // 1440 for i in intervals})
    assert days_seen == [0, 1, 2, 3, 4, 5, 6]
    assert len(intervals) == 7


def test_parse_hours_with_overnight_segment():
    intervals = parse_hours("Mon-Wed 5 pm - 12:30 am")
    # Each Mon, Tue, Wed → overnight interval ending the next day.
    assert len(intervals) == 3
    for i in intervals:
        assert i.end_week_minute - i.start_week_minute == (24 * 60 - 17 * 60) + 30


def test_parse_hours_omitted_day_produces_no_interval():
    intervals = parse_hours("Mon, Wed-Sun 11 am - 10 pm")
    days_seen = sorted({i.start_week_minute // 1440 for i in intervals})
    # Tuesday (1) is omitted.
    assert days_seen == [0, 2, 3, 4, 5, 6]
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_parser_full.py -v`
Expected: ImportError or NameError for `parse_hours`.

- [ ] **Step 3: Implement `parse_hours`**

Add to `app/parser.py`:

```python
def parse_hours(s: str) -> list[Interval]:
    """Top-level: parse a complete hours string into normalized intervals."""
    intervals: list[Interval] = []
    for segment in split_segments(s):
        days, open_time, close_time = parse_segment(segment)
        intervals.extend(build_intervals(days, open_time, close_time, segment))
    return intervals
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_parser_full.py -v`
Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/parser.py tests/test_parser_full.py
git commit -m "feat: top-level parse_hours composes segment splitting and interval building"
```

---

## Task 13: Closing time of `12 am` means next-day midnight

The string `"5 pm - 12 am"` describes a restaurant open until midnight (24:00), not one that closes at 00:00 of the same day. Make `build_intervals` interpret a closing time of `0` (midnight) as `1440` (end of the day) when paired with a non-zero opening.

**Files:**
- Modify: `app/parser.py`
- Modify: `tests/test_parser_full.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_parser_full.py`:

```python
def test_parse_hours_closes_at_midnight_means_end_of_day():
    intervals = parse_hours("Mon-Sun 5 pm - 12 am")
    assert len(intervals) == 7
    for i in intervals:
        # Each interval should close exactly at the next day's midnight.
        day = i.start_week_minute // 1440
        assert i.start_week_minute == day * 1440 + 17 * 60
        assert i.end_week_minute == (day + 1) * 1440 if day < 6 else 10080
```

- [ ] **Step 2: Run test**

Run: `pytest tests/test_parser_full.py::test_parse_hours_closes_at_midnight_means_end_of_day -v`
Expected: failing assertion — the current implementation treats `close_time == 0` as overnight wraparound, which is correct intuition but produces a Sunday split that doesn't match this test's structure.

- [ ] **Step 3: Update `build_intervals` to canonicalize `close_time == 0`**

In `app/parser.py`, modify `build_intervals` to treat a closing minute of `0` paired with a non-zero opening as end-of-day (1440) rather than overnight to next-day midnight. Add this near the top of the loop body, before the `if close_time > open_time:` check:

```python
def build_intervals(
    day_indices: list[int],
    open_time: int,
    close_time: int,
    source: str,
) -> list[Interval]:
    """Build normalized week-minute intervals from a parsed segment.

    A closing time of 0 ('12 am') paired with a non-zero opening means
    "midnight at the end of the day," not "midnight at the start of the day."
    Canonicalize that case to the same-day end-of-day boundary.

    See approach-recommended.md for the rationale.
    """
    intervals: list[Interval] = []
    for day in day_indices:
        start = to_week_minute(day, open_time)
        if close_time == 0 and open_time != 0:
            # "...- 12 am" → end of THIS day, not start of next day.
            if day == 6:
                # Sunday end-of-day is exactly WEEK_MINUTES.
                intervals.append(Interval(start, WEEK_MINUTES, source))
            else:
                intervals.append(Interval(start, to_week_minute(day + 1, 0), source))
            continue
        if close_time > open_time:
            intervals.append(Interval(start, to_week_minute(day, close_time), source))
            continue
        # Overnight (close < open): close belongs to next day.
        if day == 6:
            intervals.append(Interval(start, WEEK_MINUTES, source))
            if close_time > 0:
                intervals.append(Interval(0, close_time, source))
        else:
            intervals.append(Interval(start, to_week_minute(day + 1, close_time), source))
    return intervals
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_parser_full.py -v`
Expected: all parse_hours tests pass, including the new midnight test.

Run: `pytest tests/test_parser_segments.py -v`
Expected: all build_intervals tests still pass (regression check).

- [ ] **Step 5: Commit**

```bash
git add app/parser.py tests/test_parser_full.py
git commit -m "feat: treat closing time of 12 am as end-of-day, not next-day midnight"
```

---

## Task 14: CSV loader

Read `restaurants.csv` into a list of `(name, raw_hours)` tuples.

**Files:**
- Create: `app/loader.py`
- Create: `tests/test_loader.py`
- Create: `tests/fixtures/sample.csv`

- [ ] **Step 1: Create test fixture**

```text
"Restaurant Name","Hours"
"Test Cafe","Mon-Fri 7 am - 3 pm"
"Late Bar","Sun-Thu 5 pm - 12 am  / Fri-Sat 5 pm - 2 am"
```

Save to `tests/fixtures/sample.csv`.

- [ ] **Step 2: Write failing test**

```python
# tests/test_loader.py
from pathlib import Path

import pytest

from app.loader import build_restaurants, load_csv

FIXTURE = Path(__file__).parent / "fixtures" / "sample.csv"


def test_load_csv_returns_name_hours_tuples():
    rows = load_csv(str(FIXTURE))
    assert rows == [
        ("Test Cafe", "Mon-Fri 7 am - 3 pm"),
        ("Late Bar", "Sun-Thu 5 pm - 12 am  / Fri-Sat 5 pm - 2 am"),
    ]


def test_load_csv_skips_header():
    rows = load_csv(str(FIXTURE))
    assert rows[0][0] != "Restaurant Name"


def test_build_restaurants_parses_hours():
    rows = [("Test Cafe", "Mon-Fri 7 am - 3 pm")]
    restaurants = build_restaurants(rows)
    assert len(restaurants) == 1
    r = restaurants[0]
    assert r.name == "Test Cafe"
    assert r.raw_hours == "Mon-Fri 7 am - 3 pm"
    assert len(r.intervals) == 5  # Monday through Friday
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_loader.py -v`
Expected: ImportError for `app.loader`.

- [ ] **Step 4: Implement `app/loader.py`**

```python
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
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_loader.py -v`
Expected: all 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add app/loader.py tests/test_loader.py tests/fixtures/sample.csv
git commit -m "feat: load CSV into Restaurant objects with parsed intervals"
```

---

## Task 15: FastAPI lifespan loader

Wire `load_csv` and `build_restaurants` into the FastAPI startup so the in-memory list is populated before the first request.

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Replace `app/main.py` with the lifespan version**

```python
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
```

- [ ] **Step 2: Verify the import compiles**

Run: `python -c "from app.main import app; print(app.title)"`
Expected: `ImportError` for `app.api` (Task 16 creates it).

This is intentional — the next task adds `app/api.py`. Continue without committing yet.

---

## Task 16: API endpoint

Add the `/api/restaurants/open` route that returns a JSON list of names.

**Files:**
- Create: `app/api.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_api.py
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
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_api.py -v`
Expected: ImportError for `app.api`.

- [ ] **Step 3: Implement `app/api.py`**

```python
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_api.py -v`
Expected: all 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/api.py app/main.py tests/test_api.py
git commit -m "feat: add /api/restaurants/open endpoint with FastAPI"
```

---

## Task 17: API request validation

Verify that an invalid datetime returns 422 and a missing parameter returns 422 (FastAPI/Pydantic should do this for free, but it deserves an explicit test).

**Files:**
- Modify: `tests/test_api.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_api.py`:

```python
def test_api_invalid_datetime_returns_422(client_with_fixture):
    r = client_with_fixture.get("/api/restaurants/open?datetime=not-a-date")
    assert r.status_code == 422


def test_api_missing_datetime_returns_422(client_with_fixture):
    r = client_with_fixture.get("/api/restaurants/open")
    assert r.status_code == 422
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_api.py -v`
Expected: both new tests pass — Pydantic handles validation automatically.

- [ ] **Step 3: Commit**

```bash
git add tests/test_api.py
git commit -m "test: assert 422 for invalid and missing datetime"
```

---

## Task 18: Persona-named integration tests

Tests named after the user behaviors they verify. The test file itself documents who the API is for.

**Files:**
- Create: `tests/test_personas.py`

- [ ] **Step 1: Write the persona tests**

```python
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
```

- [ ] **Step 2: Run the persona tests**

Run: `pytest tests/test_personas.py -v`
Expected: all 8 tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_personas.py
git commit -m "test: persona-driven integration tests for Marcus, Priya, Leo"
```

---

## Task 19: Edge case test suite

Explicit tests for every edge case named in the spec's Edge Cases section.

**Files:**
- Create: `tests/test_edge_cases.py`

- [ ] **Step 1: Write the edge case tests**

```python
"""Explicit edge case tests covering each case named in approach-recommended.md."""

import pytest

from app.intervals import Interval, find_open
from app.parser import parse_hours


def _open_at(intervals: list[Interval], q: int) -> bool:
    return any(i.start_week_minute <= q < i.end_week_minute for i in intervals)


# Boundary semantics

def test_boundary_open_exactly_at_opening_minute():
    intervals = parse_hours("Mon 11 am - 10 pm")
    # Monday 11:00 = week-minute 660
    assert _open_at(intervals, 660) is True


def test_boundary_closed_exactly_at_closing_minute():
    intervals = parse_hours("Mon 11 am - 10 pm")
    # Monday 22:00 = week-minute 22 * 60 = 1320
    assert _open_at(intervals, 1320) is False


def test_boundary_open_one_minute_before_closing():
    intervals = parse_hours("Mon 11 am - 10 pm")
    assert _open_at(intervals, 1319) is True


# Overnight

def test_overnight_open_after_midnight():
    intervals = parse_hours("Mon 5 pm - 1:30 am")
    # Tuesday 01:00 = 1440 + 60 = 1500
    assert _open_at(intervals, 1500) is True


def test_overnight_closed_at_close_time():
    intervals = parse_hours("Mon 5 pm - 1:30 am")
    # Tuesday 01:30 = 1440 + 90 = 1530
    assert _open_at(intervals, 1530) is False


# All-week overnight (Seoul 116)

def test_all_week_overnight_tuesday_2am_is_open():
    intervals = parse_hours("Mon-Sun 11 am - 4 am")
    # Tuesday 02:00 = 1440 + 120 = 1560 — covered by Monday's interval.
    assert _open_at(intervals, 1560) is True


def test_all_week_overnight_tuesday_5am_is_closed():
    intervals = parse_hours("Mon-Sun 11 am - 4 am")
    # Tuesday 05:00 = 1440 + 300 = 1740 — Monday's interval ended at 04:00.
    assert _open_at(intervals, 1740) is False


# Sunday-to-Monday wraparound

def test_sunday_wraparound_monday_one_am_is_open():
    intervals = parse_hours("Sun 8 pm - 2 am")
    # Monday 01:00 = week-minute 60 — covered by the wraparound split.
    assert _open_at(intervals, 60) is True


def test_sunday_wraparound_monday_two_am_is_closed():
    intervals = parse_hours("Sun 8 pm - 2 am")
    # Monday 02:00 = week-minute 120 — exactly at the close, half-open says closed.
    assert _open_at(intervals, 120) is False


# 12 am / 12 pm conversions and closing-at-12am rule

def test_closes_at_midnight_means_end_of_day():
    intervals = parse_hours("Mon-Sun 5 pm - 12 am")
    # Monday 23:59 should still be open. Monday 23:59 = 23*60+59 = 1439.
    assert _open_at(intervals, 1439) is True


def test_closes_at_midnight_then_closed_at_next_day_start():
    intervals = parse_hours("Mon-Sat 5 pm - 12 am")  # not Sunday — avoid wraparound
    # Tuesday 00:00 = 1440 — closed (half-open semantics).
    assert _open_at(intervals, 1440) is False


def test_12_pm_is_noon():
    intervals = parse_hours("Mon 12 pm - 11 pm")
    # Monday 12:00 noon = 720
    assert _open_at(intervals, 720) is True
    # Monday 11:59 = 719 — closed (before opening)
    assert _open_at(intervals, 719) is False


# Omitted days

def test_omitted_day_produces_no_interval():
    intervals = parse_hours("Mon, Wed-Sun 11 am - 10 pm")
    days_with_intervals = sorted({i.start_week_minute // 1440 for i in intervals})
    assert 1 not in days_with_intervals  # Tuesday absent


# Circular ranges

def test_circular_day_range_fri_mon():
    intervals = parse_hours("Fri-Mon 5 pm - 11 pm")
    days_with_intervals = sorted({i.start_week_minute // 1440 for i in intervals})
    assert days_with_intervals == [0, 4, 5, 6]  # Mon, Fri, Sat, Sun
```

- [ ] **Step 2: Run the tests**

Run: `pytest tests/test_edge_cases.py -v`
Expected: all 14 tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_edge_cases.py
git commit -m "test: explicit coverage for every named edge case"
```

---

## Task 20: Property-based parser tests

Use Hypothesis to generate random valid intervals and assert the half-open query semantics hold for any of them. (We use direct Interval generation rather than synthesizing hours strings — it's the right scope for a take-home.)

**Files:**
- Create: `tests/test_property_based.py`

- [ ] **Step 1: Write the property-based tests**

```python
"""Property-based tests for the interval query semantics.

We generate random valid Intervals and verify the half-open [start, end)
contract holds for any query inside, at the start, at the end, and outside.
"""

from hypothesis import given, strategies as st

from app.intervals import Interval, Restaurant, find_open

# An integer in [0, 10079]
week_minute = st.integers(min_value=0, max_value=10079)


@st.composite
def interval_strategy(draw):
    start = draw(week_minute)
    # End is strictly greater than start, capped at WEEK_MINUTES.
    end = draw(st.integers(min_value=start + 1, max_value=10080))
    return Interval(start_week_minute=start, end_week_minute=end, source_segment="<gen>")


@given(iv=interval_strategy())
def test_query_at_start_is_open(iv):
    rs = [Restaurant("X", "<gen>", [iv])]
    assert find_open(rs, iv.start_week_minute) == ["X"]


@given(iv=interval_strategy())
def test_query_at_end_is_closed(iv):
    rs = [Restaurant("X", "<gen>", [iv])]
    assert find_open(rs, iv.end_week_minute) == []


@given(iv=interval_strategy())
def test_query_one_before_start_is_closed(iv):
    if iv.start_week_minute == 0:
        return  # No -1 query in the valid range.
    rs = [Restaurant("X", "<gen>", [iv])]
    assert find_open(rs, iv.start_week_minute - 1) == []


@given(iv=interval_strategy(), data=st.data())
def test_query_inside_interval_is_open(iv, data):
    if iv.end_week_minute - iv.start_week_minute < 2:
        return
    q = data.draw(
        st.integers(min_value=iv.start_week_minute, max_value=iv.end_week_minute - 1)
    )
    rs = [Restaurant("X", "<gen>", [iv])]
    assert find_open(rs, q) == ["X"]


@given(
    a=interval_strategy(),
    b=interval_strategy(),
    q=week_minute,
)
def test_disjoint_restaurants_match_independently(a, b, q):
    rs = [Restaurant("A", "<gen>", [a]), Restaurant("B", "<gen>", [b])]
    result = find_open(rs, q)
    a_open = a.start_week_minute <= q < a.end_week_minute
    b_open = b.start_week_minute <= q < b.end_week_minute
    expected = sorted([n for n, ok in [("A", a_open), ("B", b_open)] if ok])
    assert result == expected
```

- [ ] **Step 2: Run the property tests**

Run: `pytest tests/test_property_based.py -v`
Expected: all 5 properties hold across Hypothesis's generated examples.

- [ ] **Step 3: Commit**

```bash
git add tests/test_property_based.py
git commit -m "test: property-based interval query tests via Hypothesis"
```

---

## Task 21: Validate the real CSV parses cleanly

Smoke test that loading the actual `restaurants.csv` succeeds and yields the expected number of restaurants.

**Files:**
- Modify: `tests/test_loader.py`

- [ ] **Step 1: Append a smoke test**

Append to `tests/test_loader.py`:

```python
REAL_CSV = Path(__file__).parent.parent / "restaurants.csv"


@pytest.mark.skipif(not REAL_CSV.exists(), reason="real CSV not present in this environment")
def test_real_csv_parses_without_errors():
    rows = load_csv(str(REAL_CSV))
    assert len(rows) == 40  # The take-home CSV has 40 restaurants.
    restaurants = build_restaurants(rows)
    assert len(restaurants) == 40
    # Every restaurant should produce at least one interval.
    for r in restaurants:
        assert r.intervals, f"{r.name!r} parsed to zero intervals"
```

- [ ] **Step 2: Run the smoke test**

Run: `pytest tests/test_loader.py::test_real_csv_parses_without_errors -v`
Expected: pass — the parser handles every row in the CSV.

If this test fails, the offending restaurant + raw_hours value is in the failure message; fix the parser to handle that input before continuing.

- [ ] **Step 3: Commit**

```bash
git add tests/test_loader.py
git commit -m "test: smoke-test loading the real restaurants.csv"
```

---

## Task 22: Dockerfile

A single-stage Dockerfile that builds and runs the app.

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

- [ ] **Step 1: Create `.dockerignore`**

```text
.git
.gitignore
.pytest_cache
__pycache__
*.pyc
.venv
venv
htmlcov
.coverage
docs
tests
README.md
```

- [ ] **Step 2: Create `Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY app ./app
COPY restaurants.csv ./restaurants.csv

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Verify the build**

Run: `docker build -t restaurant-hours-api .`
Expected: build succeeds.

Run: `docker run --rm -d -p 8000:8000 --name rh-api restaurant-hours-api`
Then: `curl 'http://localhost:8000/api/restaurants/open?datetime=2026-05-06T19:30:00'`
Expected: a JSON array of restaurant names.
Then: `docker stop rh-api`

- [ ] **Step 4: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "feat: single-stage Dockerfile for FastAPI app"
```

---

## Task 23: Final verification

Run the full test suite, confirm coverage, and tag a release.

**Files:**
- (no new files)

- [ ] **Step 1: Run the full test suite**

Run: `pytest --cov=app --cov-report=term-missing`
Expected: all tests pass; coverage on `app/` should be ≥ 95%.

- [ ] **Step 2: Smoke-test the running app**

Run: `uvicorn app.main:app --port 8000 &` then `curl 'http://localhost:8000/api/restaurants/open?datetime=2026-05-06T19:30:00'` and `curl 'http://localhost:8000/docs'` to confirm OpenAPI docs render.
Expected: 200 with a JSON list, and the `/docs` page loads.

Stop the server: `kill %1` (or use `pgrep -f uvicorn`).

- [ ] **Step 3: Verify the README is in place**

Run: `ls README.md && head -10 README.md`
Expected: README.md exists and starts with the project title.

(The README is drafted in parallel by another agent — see `README.md` at the repo root.)

- [ ] **Step 4: Final commit if anything is missing**

If `git status` shows untracked files, decide whether they belong in the submission. Commit anything intentional with a message describing the addition.

---

## Notes for the Implementer

**Test discipline:** Every task follows the TDD cycle — write the failing test first, watch it fail with a meaningful error, then write the smallest implementation that makes it pass. Don't skip the "watch it fail" step; an always-passing test is invisible regression risk.

**Commit cadence:** Each task ends with a commit. Commits should compile and pass all tests. Don't bundle multiple tasks into one commit — the per-task commits document the build.

**Linting/formatting:** Not required by the assignment. If `ruff` or `black` are easy to add late, do so — but do not insert a linting task that delays the build.

**Performance:** 40 restaurants × ~6 intervals each is trivial. Don't add caching, indexing, or async optimization. The code should look small because the system is small.

**Spec source of truth:** When a question comes up about behavior the plan doesn't address, consult `/Users/stevenhagene/Projects/liine/approach-recommended.md`. If the spec is silent, pick the simpler option and add a one-line note to the README's Design Decisions section.
