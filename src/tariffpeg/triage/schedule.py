"""Finding a day an inspector can actually go.

A disposition is not a visit. Between the two sit four things that have all
stopped a visit at some point: the premises is shut for the winter, the licence
has run out, the inspector who covers that stretch of coast is on leave, and the
week is already full.

An urgent finding does not override the closed season. There is nothing to
inspect at a premises that is shut, so the visit goes to the first day it is
open again and the case file says that is what happened.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from tariffpeg.errors import Invalid
from tariffpeg.model.licence import Licence
from tariffpeg.triage.disposition import Disposition
from tariffpeg.workdays import add_working_days, is_working_day

NOTICE_DAYS = 2
"""Working days between a decision and the earliest visit it can produce."""

TARGET_DAYS = {Disposition.URGENT: 10, Disposition.REINSPECTION: 40}
"""Working days the order gives the unit to make each kind of visit."""

SEARCH_DAYS = 400
"""How far ahead the search will look before giving up."""


@dataclass(frozen=True, slots=True)
class Diary:
    """One inspector, what they cover and when they are away."""

    name: str
    weekly_capacity: int = 4
    away: frozenset[dt.date] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise Invalid("name", self.name, "an inspector has a name in the diary")
        if self.weekly_capacity < 1:
            raise Invalid(
                "weekly_capacity", self.weekly_capacity, "a diary holds one visit or more"
            )

    def free_on(self, day: dt.date) -> bool:
        """Return whether this inspector could travel on a day."""
        return day not in self.away


@dataclass(frozen=True, slots=True)
class Booking:
    """One visit, booked."""

    licence_serial: int
    inspector: str
    day: dt.date
    disposition: Disposition

    @property
    def week(self) -> tuple[int, int]:
        """Return the year and week number the visit falls in."""
        year, week, _ = self.day.isocalendar()
        return year, week


@dataclass(frozen=True, slots=True)
class Refusal:
    """Why no day could be found."""

    licence_serial: int
    reason: str


class Scheduler:
    """Books visits against the diaries, one at a time."""

    def __init__(
        self,
        diaries: Sequence[Diary],
        holidays: frozenset[dt.date] = frozenset(),
    ) -> None:
        if not diaries:
            raise Invalid("diaries", 0, "there is nobody to send")
        self.diaries = tuple(sorted(diaries, key=lambda diary: diary.name))
        self.holidays = holidays
        self.booked: list[Booking] = []

    def load(self, inspector: str, week: tuple[int, int]) -> int:
        """Return how many visits an inspector already has in a week."""
        return sum(
            1 for booking in self.booked if booking.inspector == inspector and booking.week == week
        )

    def can_visit(self, licence: Licence, day: dt.date) -> bool:
        """Return whether a visit to this premises could happen on a day."""
        if not is_working_day(day, self.holidays):
            return False
        return licence.is_trading_on(day)

    def book(
        self,
        licence: Licence,
        disposition: Disposition,
        decided_on: dt.date,
    ) -> Booking | Refusal:
        """Book the earliest visit this disposition can have, or say why not."""
        if disposition not in TARGET_DAYS:
            return Refusal(licence.serial, f"a {disposition} does not send anybody out")
        earliest = add_working_days(decided_on, NOTICE_DAYS, self.holidays)
        day = earliest
        for _ in range(SEARCH_DAYS):
            if self.can_visit(licence, day):
                inspector = self._free_inspector(day)
                if inspector is not None:
                    booking = Booking(licence.serial, inspector, day, disposition)
                    self.booked.append(booking)
                    return booking
            day += dt.timedelta(days=1)
        return Refusal(licence.serial, "no day inside the licence period had anybody free")

    def _free_inspector(self, day: dt.date) -> str | None:
        year, week, _ = day.isocalendar()
        for diary in self.diaries:
            if not diary.free_on(day):
                continue
            if self.load(diary.name, (year, week)) < diary.weekly_capacity:
                return diary.name
        return None

    def overdue(self, booking: Booking, decided_on: dt.date) -> bool:
        """Return whether a booking falls outside the target the order sets."""
        target = add_working_days(decided_on, TARGET_DAYS[booking.disposition], self.holidays)
        return booking.day > target

    def report(self, decided_on: dt.date) -> tuple[str, ...]:
        """Return one line per booking, saying whether it made the target."""
        lines = []
        for booking in sorted(self.booked, key=lambda item: (item.day, item.licence_serial)):
            state = "late" if self.overdue(booking, decided_on) else "in time"
            lines.append(
                f"{booking.licence_serial} to {booking.inspector} on {booking.day}, {state}"
            )
        return tuple(lines)


def diaries_by_name(diaries: Sequence[Diary]) -> Mapping[str, Diary]:
    """Return the diaries indexed by inspector name."""
    return {diary.name: diary for diary in diaries}


@dataclass(frozen=True, slots=True)
class Round:
    """One scheduling run: what was booked, what was not, and what missed its target."""

    bookings: tuple[Booking, ...] = ()
    refusals: tuple[Refusal, ...] = ()
    late: frozenset[int] = field(default_factory=frozenset)

    @property
    def booked(self) -> int:
        """Return how many visits came out of the run."""
        return len(self.bookings)

    @property
    def all_in_time(self) -> bool:
        """Return whether every visit the run booked made its target."""
        return not self.late

    def refusal_lines(self) -> tuple[str, ...]:
        """Return one line for each licence nobody could be sent to."""
        return tuple(f"{item.licence_serial}: {item.reason}" for item in self.refusals)


def book_all(
    scheduler: Scheduler,
    wanted: Sequence[tuple[Licence, Disposition]],
    decided_on: dt.date,
) -> Round:
    """Book every visit a set of dispositions asks for, in the order given.

    The order matters and it is the caller's to choose. The scheduler fills the
    first free diary it finds, so whichever licence is offered first gets the
    earliest day, and the run puts the heaviest case at the front.
    """
    bookings: list[Booking] = []
    refusals: list[Refusal] = []
    late: set[int] = set()
    for licence, disposition in wanted:
        if disposition not in TARGET_DAYS:
            continue
        outcome = scheduler.book(licence, disposition, decided_on)
        if isinstance(outcome, Booking):
            bookings.append(outcome)
            if scheduler.overdue(outcome, decided_on):
                late.add(outcome.licence_serial)
        else:
            refusals.append(outcome)
    return Round(tuple(bookings), tuple(refusals), frozenset(late))
