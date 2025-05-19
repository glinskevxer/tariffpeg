"""Stay months and the season they fall in.

Channels do not publish the day a guest arrived. They publish the month, and
they publish it in whatever shape their templates use. Everything downstream
works in stay months rather than dates, because a sampling regime that asks for
a date it can never have is a regime nobody can satisfy.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Self

from tariffpeg.errors import Invalid

MONTH_NAMES = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
"""Month names as the channels we read spell them."""

_BY_NAME = {name: number for number, name in enumerate(MONTH_NAMES, start=1)}
_BY_ABBREVIATION = {name[:3]: number for number, name in enumerate(MONTH_NAMES, start=1)}
_ISO = re.compile(r"^(\d{4})-(\d{1,2})$")
_SLASHED = re.compile(r"^(\d{1,2})/(\d{4})$")
_NAMED = re.compile(r"^([A-Za-z]+)\.?,?\s+(\d{4})$")
_NAMED_FIRST = re.compile(r"^(\d{4})\s+([A-Za-z]+)$")


class Season(StrEnum):
    """Which part of the trading year a stay falls in."""

    PEAK = "peak"
    SHOULDER = "shoulder"
    OFF = "off"


@dataclass(frozen=True, slots=True, order=True)
class StayMonth:
    """The month a guest stayed in."""

    year: int
    month: int

    def __post_init__(self) -> None:
        if not 1900 <= self.year <= 2200:
            raise Invalid("year", self.year, "this is not a year a stay happened in")
        if not 1 <= self.month <= 12:
            raise Invalid("month", self.month, "a month runs from one to twelve")

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    @property
    def ordinal(self) -> int:
        """Return the month as a count from year zero, for arithmetic."""
        return self.year * 12 + (self.month - 1)

    @classmethod
    def from_ordinal(cls, ordinal: int) -> Self:
        """Return the stay month for a count from year zero."""
        return cls(ordinal // 12, ordinal % 12 + 1)

    @classmethod
    def of(cls, day: dt.date) -> Self:
        """Return the stay month a date falls in."""
        return cls(day.year, day.month)

    def plus(self, months: int) -> StayMonth:
        """Return the stay month this many months later."""
        return StayMonth.from_ordinal(self.ordinal + months)

    def minus(self, months: int) -> StayMonth:
        """Return the stay month this many months earlier."""
        return self.plus(-months)

    def months_since(self, other: StayMonth) -> int:
        """Return how many months this one is after another."""
        return self.ordinal - other.ordinal

    def first_day(self) -> dt.date:
        """Return the first day of the month."""
        return dt.date(self.year, self.month, 1)

    def last_day(self) -> dt.date:
        """Return the last day of the month."""
        return self.plus(1).first_day() - dt.timedelta(days=1)

    def season(self) -> Season:
        """Return the season this month falls in on the default calendar."""
        return DEFAULT_SEASONS.season_of(self.month)


def month_number(name: str) -> int:
    """Return the number of a month written as a word, or refuse it."""
    cleaned = name.strip().lower().rstrip(".")
    if cleaned in _BY_NAME:
        return _BY_NAME[cleaned]
    if cleaned[:3] in _BY_ABBREVIATION and len(cleaned) <= 4:
        return _BY_ABBREVIATION[cleaned[:3]]
    raise Invalid("month", name, "this is not a month name this reader knows")


def parse_stay_month(text: str) -> StayMonth:
    """Read a stay month out of whatever shape a channel printed it in."""
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        raise Invalid("stay_month", text, "the page carried no stay month")
    iso = _ISO.match(cleaned)
    if iso:
        return StayMonth(int(iso.group(1)), int(iso.group(2)))
    slashed = _SLASHED.match(cleaned)
    if slashed:
        return StayMonth(int(slashed.group(2)), int(slashed.group(1)))
    named = _NAMED.match(cleaned)
    if named:
        return StayMonth(int(named.group(2)), month_number(named.group(1)))
    reversed_named = _NAMED_FIRST.match(cleaned)
    if reversed_named:
        return StayMonth(int(reversed_named.group(1)), month_number(reversed_named.group(2)))
    raise Invalid("stay_month", text, "this is not a shape this reader knows")


@dataclass(frozen=True, slots=True)
class SeasonCalendar:
    """Which months the unit counts as peak, shoulder and off."""

    peak: frozenset[int]
    shoulder: frozenset[int]

    def __post_init__(self) -> None:
        for name, months in (("peak", self.peak), ("shoulder", self.shoulder)):
            for month in months:
                if not 1 <= month <= 12:
                    raise Invalid(name, month, "a month runs from one to twelve")
        overlap = self.peak & self.shoulder
        if overlap:
            raise Invalid("peak", sorted(overlap)[0], "a month sits in one season only")
        if not self.peak:
            raise Invalid("peak", 0, "a trading year has a peak in it")

    def season_of(self, month: int) -> Season:
        """Return the season a month falls in."""
        if not 1 <= month <= 12:
            raise Invalid("month", month, "a month runs from one to twelve")
        if month in self.peak:
            return Season.PEAK
        if month in self.shoulder:
            return Season.SHOULDER
        return Season.OFF

    def months_in(self, season: Season) -> tuple[int, ...]:
        """Return the months that fall in a season, in calendar order."""
        return tuple(month for month in range(1, 13) if self.season_of(month) is season)


DEFAULT_SEASONS = SeasonCalendar(frozenset({7, 8}), frozenset({5, 6, 9, 10}))
"""The calendar the licensing order sets for the coast. July and August are the
peak, the two months either side of them are the shoulder, and the rest is off."""


def month_range(start: StayMonth, end: StayMonth) -> tuple[StayMonth, ...]:
    """Return every stay month from one to another, both ends included."""
    if end < start:
        raise Invalid("end", str(end), "a range of months ends after it starts")
    return tuple(StayMonth.from_ordinal(n) for n in range(start.ordinal, end.ordinal + 1))
