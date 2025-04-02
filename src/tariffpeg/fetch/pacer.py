"""Deciding whether a request may go out now, and if not, when.

Three things can hold a request back and they are not the same thing. The crawl
delay is a gap between one request and the next. The courtesy window is a block
of hours the channel asked to be left alone outside of. The daily ceiling is a
count that resets at midnight. A caller that is told to wait is told which of
the three it is waiting on, because the harvest report has to say why a licence
came back short.

The pacer holds no clock of its own. Every question carries the instant it is
being asked at, which is what lets a harvest be replayed.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum

from tariffpeg.errors import Invalid
from tariffpeg.model.channel import FetchPolicy


class Hold(StrEnum):
    """Why a request is not going out yet."""

    READY = "ready"
    CRAWL_DELAY = "crawl_delay"
    COURTESY_WINDOW = "courtesy_window"
    DAILY_CEILING = "daily_ceiling"


@dataclass(frozen=True, slots=True)
class Grant:
    """The pacer's answer to one request."""

    hold: Hold
    wait_ms: int
    resume_at: dt.datetime | None = None

    @property
    def allowed(self) -> bool:
        """Return whether the request may go out at the instant it was asked about."""
        return self.hold is Hold.READY

    @property
    def exhausted(self) -> bool:
        """Return whether waiting will not help before the day rolls over."""
        return self.hold is Hold.DAILY_CEILING


@dataclass(slots=True)
class HostState:
    """What the pacer remembers about one host."""

    last_request: dt.datetime | None = None
    day: dt.date | None = None
    spent: int = 0


class Pacer:
    """Holds back requests until the agreed terms allow them out."""

    def __init__(self) -> None:
        self._hosts: dict[str, HostState] = {}

    def state(self, host: str) -> HostState:
        """Return the remembered state for a host, creating it if new."""
        if host not in self._hosts:
            self._hosts[host] = HostState()
        return self._hosts[host]

    def spent_today(self, host: str, at: dt.datetime) -> int:
        """Return how many requests have gone to this host on this UTC day."""
        state = self.state(host)
        if state.day != at.date():
            return 0
        return state.spent

    def ask(
        self,
        host: str,
        policy: FetchPolicy,
        at: dt.datetime,
        delay_ms: int | None = None,
    ) -> Grant:
        """Return whether a request to this host may go out at this instant."""
        if at.tzinfo is None:
            raise Invalid("at", at, "the pacer is asked in UTC")
        state = self.state(host)
        effective_delay = policy.delay_with(delay_ms)
        if self.spent_today(host, at) >= policy.daily_request_ceiling:
            tomorrow = dt.datetime.combine(
                at.date() + dt.timedelta(days=1), dt.time(0, 0), tzinfo=dt.UTC
            )
            return Grant(Hold.DAILY_CEILING, _ms_between(at, tomorrow), tomorrow)
        if not policy.window.is_open_at(at):
            opens = policy.window.next_open(at)
            return Grant(Hold.COURTESY_WINDOW, _ms_between(at, opens), opens)
        if state.last_request is not None:
            earliest = state.last_request + dt.timedelta(milliseconds=effective_delay)
            if at < earliest:
                return Grant(Hold.CRAWL_DELAY, _ms_between(at, earliest), earliest)
        return Grant(Hold.READY, 0, at)

    def record(self, host: str, at: dt.datetime) -> None:
        """Note that a request went out to this host."""
        state = self.state(host)
        if state.day != at.date():
            state.day = at.date()
            state.spent = 0
        state.spent += 1
        state.last_request = at

    def forget(self, host: str) -> None:
        """Drop what is remembered about a host."""
        self._hosts.pop(host, None)

    def hosts(self) -> tuple[str, ...]:
        """Return the hosts the pacer is holding state for."""
        return tuple(sorted(self._hosts))


def _ms_between(start: dt.datetime, end: dt.datetime) -> int:
    """Return the whole milliseconds from one instant to another, never negative."""
    delta = (end - start).total_seconds() * 1000
    return max(0, int(delta + 0.5))
