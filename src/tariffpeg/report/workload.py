"""What the booked visits do to the diaries, week by week.

The scheduler books the earliest day it can find and moves on. Nobody looking
at its output can see that one inspector has taken eleven visits in a fortnight
while another has taken two, which is the thing the unit manager needs to know
before the visits go out.

Spare capacity is counted over the whole span the bookings cover, not over the
weeks an inspector happens to have work in. An inspector with nothing booked has
a week of spare capacity for every week in the span, and that is the reading
that says the run is lopsided.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from tariffpeg.report.rows import Column
from tariffpeg.triage.schedule import Booking, Diary

COLUMNS = (
    Column("inspector", "inspector"),
    Column("visits", "visits", numeric=True),
    Column("late", "late", numeric=True),
    Column("busiest", "busiest week", numeric=True),
    Column("spare", "spare", numeric=True),
    Column("first", "first"),
    Column("last", "last"),
)
"""The columns the workload prints as."""


@dataclass(frozen=True, slots=True)
class Week:
    """One inspector's week: what is in it and what the diary allows."""

    year: int
    number: int
    booked: int
    capacity: int

    @property
    def spare(self) -> int:
        """Return how many more visits this week could take."""
        return max(0, self.capacity - self.booked)

    @property
    def full(self) -> bool:
        """Return whether the week has no room left in it."""
        return self.booked >= self.capacity

    def label(self) -> str:
        """Return the week as the report writes it."""
        return f"{self.year}w{self.number:02d}"


@dataclass(frozen=True, slots=True)
class Load:
    """Everything one inspector was given by one scheduling run."""

    inspector: str
    weeks: tuple[Week, ...]
    late: int = 0

    @property
    def visits(self) -> int:
        """Return how many visits this inspector was given."""
        return sum(week.booked for week in self.weeks)

    @property
    def busiest(self) -> int:
        """Return the most visits any one week holds."""
        return max((week.booked for week in self.weeks), default=0)

    @property
    def spare(self) -> int:
        """Return the room left across the whole span."""
        return sum(week.spare for week in self.weeks)

    @property
    def full_weeks(self) -> tuple[str, ...]:
        """Return the weeks with no room left in them."""
        return tuple(week.label() for week in self.weeks if week.full)

    @property
    def idle(self) -> bool:
        """Return whether this inspector was given nothing at all."""
        return self.visits == 0

    def row(self, first: dt.date | None, last: dt.date | None) -> dict[str, object]:
        """Return the row this inspector prints as."""
        return {
            "inspector": self.inspector,
            "visits": self.visits,
            "late": self.late,
            "busiest": self.busiest,
            "spare": self.spare,
            "first": first.isoformat() if first else "none",
            "last": last.isoformat() if last else "none",
        }


@dataclass(frozen=True, slots=True)
class Spread:
    """The whole run, as the manager reads it before the visits go out."""

    loads: tuple[Load, ...]
    span: tuple[tuple[int, int], ...]
    days: dict[str, tuple[dt.date | None, dt.date | None]]

    def rows(self) -> list[dict[str, object]]:
        """Return one row for each inspector."""
        return [load.row(*self.days.get(load.inspector, (None, None))) for load in self.loads]

    def idle(self) -> tuple[str, ...]:
        """Return the inspectors this run gave nothing to."""
        return tuple(load.inspector for load in self.loads if load.idle)

    def lopsided(self) -> bool:
        """Return whether the run left somebody idle while somebody else filled a week.

        This is the reading that sends a run back to be done again. A full week
        beside an empty diary is not a capacity problem, it is the scheduler
        taking the first name on the list every time.
        """
        if not self.idle():
            return False
        return any(load.full_weeks for load in self.loads)


def weeks_between(first: dt.date, last: dt.date) -> tuple[tuple[int, int], ...]:
    """Return every ISO week from one day to another, in order."""
    out: list[tuple[int, int]] = []
    day = first - dt.timedelta(days=first.weekday())
    while day <= last:
        year, number, _ = day.isocalendar()
        out.append((year, number))
        day += dt.timedelta(days=7)
    return tuple(out)


def spread(
    bookings: Sequence[Booking],
    diaries: Sequence[Diary],
    late: Collection[int] = (),
) -> Spread:
    """Return what a scheduling run did to each diary."""
    days = [booking.day for booking in bookings]
    span = weeks_between(min(days), max(days)) if days else ()
    late_serials = set(late)
    loads: list[Load] = []
    when: dict[str, tuple[dt.date | None, dt.date | None]] = {}
    for diary in sorted(diaries, key=lambda item: item.name):
        mine = [booking for booking in bookings if booking.inspector == diary.name]
        by_week = {week: 0 for week in span}
        for booking in mine:
            by_week[booking.week] = by_week.get(booking.week, 0) + 1
        loads.append(
            Load(
                inspector=diary.name,
                weeks=tuple(
                    Week(year, number, by_week[(year, number)], diary.weekly_capacity)
                    for year, number in sorted(by_week)
                ),
                late=sum(1 for booking in mine if booking.licence_serial in late_serials),
            )
        )
        mine_days = [booking.day for booking in mine]
        when[diary.name] = (min(mine_days), max(mine_days)) if mine_days else (None, None)
    loads.sort(key=lambda load: (-load.visits, load.inspector))
    return Spread(tuple(loads), span, when)
