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
