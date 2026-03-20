"""Counting working days, which two different parts of this needed.

It started in the scheduler, because that is where a visit gets a day. Then the
correspondence register wanted the same arithmetic for a reply clock, and a
model that reached up into the triage layer to get it would have been the wrong
shape. So it lives here, where both can see it and neither owns it.
"""

from __future__ import annotations

import datetime as dt

from tariffpeg.errors import Invalid

WEEKEND = (5, 6)
"""The days the unit does not work, as python numbers them."""


def is_working_day(day: dt.date, holidays: frozenset[dt.date] = frozenset()) -> bool:
    """Return whether the unit works on a day."""
    return day.weekday() not in WEEKEND and day not in holidays


def add_working_days(
    start: dt.date, count: int, holidays: frozenset[dt.date] = frozenset()
) -> dt.date:
    """Return the day a number of working days after another.

    The start day is not counted, whether or not it is a working day. Counting
    forward from a Friday by one lands on the Monday.
    """
    if count < 0:
        raise Invalid("count", count, "working days are counted forwards")
    day = start
    left = count
    while left:
        day += dt.timedelta(days=1)
        if is_working_day(day, holidays):
            left -= 1
    return day


def working_days_between(
    start: dt.date, end: dt.date, holidays: frozenset[dt.date] = frozenset()
) -> int:
    """Return how many working days lie between two days, the first excluded."""
    if end < start:
        raise Invalid("end", end.isoformat(), "a span of working days ends after it starts")
    day = start
    counted = 0
    while day < end:
        day += dt.timedelta(days=1)
        if is_working_day(day, holidays):
            counted += 1
    return counted
