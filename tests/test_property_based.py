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
