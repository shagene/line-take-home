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


def split_segments(s: str) -> list[str]:
    """Split 'A / B / C' into ['A', 'B', 'C'], stripped of whitespace.

    A solitary string with no '/' returns a single-element list.
    Empty segments (caused by '//' or trailing slashes) raise ValueError.
    """
    parts = [p.strip() for p in s.split("/")]
    if any(p == "" for p in parts):
        raise ValueError(f"empty segment in hours string: {s!r}")
    return parts


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
    lower = s.lower()
    open_idx = lower.find(open_str.lower())
    close_idx = lower.find(close_str.lower(), open_idx + len(open_str))
    between = s[open_idx + len(open_str) : close_idx]
    if "-" not in between:
        raise ValueError(f"expected '-' between open and close times in segment: {s!r}")
    day_expr = s[:open_idx].rstrip(" -")
    open_time = parse_time(open_str)
    close_time = parse_time(close_str)
    days = expand_days(day_expr)
    return days, open_time, close_time
