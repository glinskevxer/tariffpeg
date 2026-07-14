"""What a plan would cost each channel against what the day has left.

The pacer refuses a request that would take a channel past its daily ceiling,
which is correct and far too late. By the time it refuses, the run has spent
its morning on the first two channels in the plan and the licence that actually
needed a second voice is at the bottom of the list, unread.

So the cost is worked out before anything is fetched. A stop that does not fit
inside what the day has left is shortened rather than dropped, because half the
pages of a listing still reads the newest reviews on it, and a stop shortened to
nothing is dropped and said so.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from tariffpeg.harvest.plan import Plan, Stop
from tariffpeg.model.channel import Channel


@dataclass(frozen=True, slots=True)
class Allowance:
    """One channel's day: what it allows, what it has had, and what is wanted."""

    channel: str
    ceiling: int
    spent: int
    wanted: int

    @property
    def remaining(self) -> int:
        """Return how many requests the day has left on this channel."""
        return max(0, self.ceiling - self.spent)

    @property
    def granted(self) -> int:
        """Return how much of what was wanted will fit."""
        return min(self.wanted, self.remaining)

    @property
    def refused(self) -> int:
        """Return how many pages will not fit inside the day."""
        return self.wanted - self.granted

    @property
    def over(self) -> bool:
        """Return whether the plan asks this channel for more than the day allows."""
        return self.refused > 0

    @property
    def exhausted(self) -> bool:
        """Return whether the day is already spent on this channel."""
        return self.remaining == 0

    def line(self) -> str:
        """Return the allowance as the harvest log writes it."""
        if not self.over:
            return f"{self.channel}: {self.granted} of {self.remaining} left today"
        return (
            f"{self.channel}: {self.granted} of {self.wanted} pages fit,"
            f" {self.refused} wait for tomorrow"
        )


@dataclass(frozen=True, slots=True)
class Budget:
    """What a whole plan costs, channel by channel."""

    allowances: tuple[Allowance, ...] = ()

    def for_channel(self, slug: str) -> Allowance | None:
        """Return one channel's allowance, if the plan visits it."""
        for allowance in self.allowances:
            if allowance.channel == slug:
                return allowance
        return None

    @property
    def wanted(self) -> int:
        """Return how many pages the plan asks for in total."""
        return sum(allowance.wanted for allowance in self.allowances)

    @property
    def granted(self) -> int:
        """Return how many pages the day will actually allow."""
        return sum(allowance.granted for allowance in self.allowances)

    @property
    def fits(self) -> bool:
        """Return whether the whole plan fits inside the day."""
        return all(not allowance.over for allowance in self.allowances)

    def over_ceiling(self) -> tuple[str, ...]:
        """Return the channels the plan asks too much of."""
        return tuple(allowance.channel for allowance in self.allowances if allowance.over)

    def lines(self) -> tuple[str, ...]:
        """Return the budget as the harvest log writes it."""
        return tuple(allowance.line() for allowance in self.allowances)


def measure(
    plan: Plan,
    channels: Mapping[str, Channel],
    spent: Mapping[str, int],
) -> Budget:
    """Return what a plan would cost each channel it visits.

    A channel the plan visits but the register does not carry is left out. The
    runner refuses that stop for its own reasons and a budget line about a
    channel nobody can fetch from is noise in the log.
    """
    wanted: dict[str, int] = {}
    for stop in plan.stops:
        if stop.channel in channels:
            wanted[stop.channel] = wanted.get(stop.channel, 0) + stop.pages
    return Budget(
        tuple(
            Allowance(
                channel=slug,
                ceiling=channels[slug].policy.daily_request_ceiling,
                spent=spent.get(slug, 0),
                wanted=asked,
            )
            for slug, asked in sorted(wanted.items())
        )
    )


def trim(plan: Plan, budget: Budget) -> Plan:
    """Return the plan cut down to what the day will allow.

    Stops are taken in plan order, so the shortening falls on the licences the
    planner put last. That is the point of the priority: the licence with no
    second channel is at the front and keeps its pages.
    """
    left = {allowance.channel: allowance.remaining for allowance in budget.allowances}
    kept: list[Stop] = []
    dropped: list[str] = []
    for stop in plan.stops:
        if stop.channel not in left:
            kept.append(stop)
            continue
        room = left[stop.channel]
        if room <= 0:
            dropped.append(
                f"{stop.licence_serial} on {stop.channel}:"
                " the day's requests are spent on this channel"
            )
            continue
        if room < stop.pages:
            dropped.append(
                f"{stop.licence_serial} on {stop.channel}:"
                f" shortened from {stop.pages} pages to {room}"
            )
            kept.append(replace(stop, pages=room))
        else:
            kept.append(stop)
        left[stop.channel] = room - min(room, stop.pages)
    return Plan(tuple(kept), (*plan.skipped, *dropped))


def spend_by_channel(slugs: Sequence[str], counted: Mapping[str, int]) -> dict[str, int]:
    """Return what each channel has already had today, zero where nothing has."""
    return {slug: counted.get(slug, 0) for slug in slugs}
