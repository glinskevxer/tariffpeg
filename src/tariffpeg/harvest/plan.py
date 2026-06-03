"""Deciding where a harvest goes before any of the budget is spent.

The plan is built from the shortfall, not from the register. A licence that is
already properly sampled is not visited, however long it has been since anybody
looked at it, because the crawl budget is small and there is always a licence
that is short.

The first thing that gets budget is a licence with no second independent
channel. One channel saying a thing is one channel saying a thing, and no amount
of further reading on that same channel turns it into two.
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from tariffpeg.model.channel import Channel
from tariffpeg.model.licence import Licence, LicenceStatus
from tariffpeg.model.listing import Listing
from tariffpeg.sample.coverage import Coverage

REVIEWS_A_PAGE = 10
"""What a review page is assumed to carry when working out how many to walk."""


@dataclass(frozen=True, slots=True)
class Stop:
    """One page a harvest intends to visit."""

    licence_serial: int
    channel: str
    url: str
    priority: int
    pages: int
    reason: str

    def sort_key(self) -> tuple[int, int, str]:
        """Return the key the plan orders stops by."""
        return self.priority, self.licence_serial, self.channel


@dataclass(frozen=True, slots=True)
class Plan:
    """Where a harvest is going, and what it decided not to visit."""

    stops: tuple[Stop, ...] = ()
    skipped: tuple[str, ...] = ()

    @property
    def total_pages(self) -> int:
        """Return the most pages this plan will ask for."""
        return sum(stop.pages for stop in self.stops)

    def for_channel(self, slug: str) -> tuple[Stop, ...]:
        """Return the stops on one channel, in plan order."""
        return tuple(stop for stop in self.stops if stop.channel == slug)

    def for_licence(self, serial: int) -> tuple[Stop, ...]:
        """Return the stops for one licence, in plan order."""
        return tuple(stop for stop in self.stops if stop.licence_serial == serial)

    def narrowed(self, serial: int = 0, channel: str = "") -> Plan:
        """Return the plan with only the stops a caller asked for.

        Narrowing is done on the built plan rather than before it, so the lines
        saying what was left out are the same lines whether or not anybody
        narrowed anything.
        """
        kept = tuple(
            stop
            for stop in self.stops
            if (not serial or stop.licence_serial == serial)
            and (not channel or stop.channel == channel)
        )
        dropped = tuple(
            f"{stop.licence_serial} on {stop.channel}: left out of this run"
            for stop in self.stops
            if stop not in kept
        )
        return Plan(kept, (*self.skipped, *dropped))

    def channels(self) -> tuple[str, ...]:
        """Return the channels this plan will visit."""
        return tuple(sorted({stop.channel for stop in self.stops}))

    def explain(self) -> tuple[str, ...]:
        """Return one line per stop, for the harvest log."""
        return tuple(
            f"{stop.licence_serial} on {stop.channel}: {stop.pages} pages, {stop.reason}"
            for stop in self.stops
        )


def pages_for(shortfall: int, channel: Channel) -> int:
    """Return how many pages to walk for a shortfall, inside the agreed limit."""
    wanted = max(1, math.ceil(shortfall / REVIEWS_A_PAGE))
    return min(wanted, channel.policy.max_pages_per_property)


def build(
    licences: Sequence[Licence],
    listings: Mapping[int, Sequence[Listing]],
    channels: Mapping[str, Channel],
    coverages: Mapping[int, Coverage],
    on: dt.date,
) -> Plan:
    """Return the plan for one harvest run."""
    stops: list[Stop] = []
    skipped: list[str] = []
    for licence in sorted(licences, key=lambda item: item.serial):
        if licence.status is not LicenceStatus.ACTIVE:
            skipped.append(f"{licence.serial}: the licence is {licence.status}")
            continue
        coverage = coverages.get(licence.serial)
        if coverage is None:
            skipped.append(f"{licence.serial}: nothing has measured this licence yet")
            continue
        if coverage.satisfied:
            skipped.append(f"{licence.serial}: the sample is complete")
            continue
        held = set(coverage.channels_held)
        for listing in sorted(listings.get(licence.serial, ()), key=lambda item: item.channel):
            if not listing.active:
                skipped.append(f"{licence.serial} on {listing.channel}: the listing is retired")
                continue
            if listing.stale_on(on):
                skipped.append(f"{licence.serial} on {listing.channel}: the listing needs checking")
                continue
            channel = channels.get(listing.channel)
            if channel is None:
                skipped.append(f"{licence.serial} on {listing.channel}: no such channel")
                continue
            wants_a_voice = coverage.channel_shortfall > 0 and listing.channel not in held
            stops.append(
                Stop(
                    licence_serial=licence.serial,
                    channel=listing.channel,
                    url=listing.url(channel),
                    priority=0 if wants_a_voice else 1,
                    pages=pages_for(coverage.total_shortfall, channel),
                    reason=_reason(coverage, wants_a_voice),
                )
            )
    stops.sort(key=Stop.sort_key)
    return Plan(tuple(stops), tuple(skipped))


def _reason(coverage: Coverage, wants_a_voice: bool) -> str:
    if wants_a_voice:
        return f"{coverage.channel_shortfall} more independent channels wanted"
    short = coverage.short_seasons()
    if not short:
        return "the sample is short"
    seasons = ", ".join(str(season) for season in short)
    return f"{coverage.total_shortfall} reviews short, worst in {seasons}"
