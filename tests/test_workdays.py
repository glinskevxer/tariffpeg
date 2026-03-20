"""Two different parts of this needed the same arithmetic, so neither owns it."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.workdays import add_working_days, is_working_day, working_days_between

FRIDAY = dt.date(2026, 6, 5)
SATURDAY = dt.date(2026, 6, 6)
MONDAY = dt.date(2026, 6, 8)


def test_a_weekend_is_not_a_working_day() -> None:
    assert is_working_day(FRIDAY)
    assert not is_working_day(SATURDAY)
    assert not is_working_day(dt.date(2026, 6, 7))
    assert is_working_day(MONDAY)


def test_a_holiday_is_not_a_working_day() -> None:
    assert not is_working_day(MONDAY, frozenset({MONDAY}))


def test_counting_forward_from_a_friday_lands_on_the_monday() -> None:
    assert add_working_days(FRIDAY, 1) == MONDAY


def test_counting_nothing_stays_where_it_started() -> None:
    assert add_working_days(SATURDAY, 0) == SATURDAY


def test_counting_forward_steps_over_a_holiday() -> None:
    assert add_working_days(FRIDAY, 1, frozenset({MONDAY})) == dt.date(2026, 6, 9)


def test_counting_working_days_backwards_is_refused() -> None:
    with pytest.raises(Invalid, match="counted forwards"):
        add_working_days(FRIDAY, -1)


def test_the_span_between_two_days_counts_the_working_ones() -> None:
    assert working_days_between(FRIDAY, MONDAY) == 1
    assert working_days_between(MONDAY, dt.date(2026, 6, 12)) == 4


def test_the_span_from_a_day_to_itself_is_nothing() -> None:
    assert working_days_between(FRIDAY, FRIDAY) == 0


def test_a_span_that_ends_before_it_starts_is_refused() -> None:
    with pytest.raises(Invalid, match="ends after it starts"):
        working_days_between(MONDAY, FRIDAY)


def test_a_span_over_a_holiday_does_not_count_it() -> None:
    assert working_days_between(FRIDAY, dt.date(2026, 6, 9), frozenset({MONDAY})) == 1


def test_the_two_functions_agree_with_each_other() -> None:
    for count in range(0, 12):
        landed = add_working_days(FRIDAY, count)
        assert working_days_between(FRIDAY, landed) == count
