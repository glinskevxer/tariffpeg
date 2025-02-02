"""The clock, passed in rather than read.

Everything here is decided against a time: whether a courtesy window is open,
whether evidence has decayed, whether a licence period has closed. None of it
calls ``datetime.now`` directly, because a test that cannot move the clock ends
up asserting something weaker than the rule it is checking.
"""

from __future__ import annotations

import datetime as dt
from typing import Protocol


class Clock(Protocol):
    """Something that can say what time it is, in UTC."""

    def now(self) -> dt.datetime:
        """Return the current instant as an aware UTC datetime."""


class SystemClock:
    """The real clock. Used by the CLI and by nothing under test."""

    def now(self) -> dt.datetime:
        """Return the wall clock instant in UTC."""
        return dt.datetime.now(dt.UTC)


class FixedClock:
    """A clock that stays where it was put until something moves it."""

    def __init__(self, at: dt.datetime) -> None:
        self._at = require_utc(at, "at")

    def now(self) -> dt.datetime:
        """Return the instant this clock is parked on."""
        return self._at

    def advance(self, **delta: float) -> dt.datetime:
        """Move the clock forward and return the new instant.

        Keyword arguments are the ones ``timedelta`` takes. Moving backwards is
        allowed, because a test for an out of order capture has to.
        """
        self._at = self._at + dt.timedelta(**delta)
        return self._at

    def set(self, at: dt.datetime) -> None:
        """Park the clock on a specific instant."""
        self._at = require_utc(at, "at")


def require_utc(value: dt.datetime, field: str = "instant") -> dt.datetime:
    """Return the datetime if it is aware and in UTC, else raise.

    Naive datetimes are refused rather than assumed to be UTC. A channel that
    prints a local timestamp with no offset is a channel whose profile has to
    say which offset to apply.
    """
    if value.tzinfo is None:
        raise ValueError(f"{field} has no timezone")
    if value.utcoffset() != dt.timedelta(0):
        raise ValueError(f"{field} is not in UTC, it is at offset {value.utcoffset()}")
    return value


def to_utc(value: dt.datetime) -> dt.datetime:
    """Convert an aware datetime to UTC, refusing naive ones."""
    if value.tzinfo is None:
        raise ValueError("a naive datetime cannot be converted, its offset is unknown")
    return value.astimezone(dt.UTC)


def isoformat(value: dt.datetime) -> str:
    """Render an instant the way the store and the ledger write it.

    Seconds resolution, a trailing ``Z``, no microseconds. The ledger is read by
    people and sorted as text, and microseconds make both worse.
    """
    return require_utc(value).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_instant(text: str) -> dt.datetime:
    """Read back an instant written by :func:`isoformat`."""
    cleaned = text.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(cleaned)
    if parsed.tzinfo is None:
        raise ValueError(f"{text!r} does not carry an offset")
    return parsed.astimezone(dt.UTC)
