"""Measuring what is held against what the regime asks for.

Two things here are easy to get wrong and both are the same mistake made twice.
The count is over opinions, not over rows: a review syndicated onto four
channels is one review towards the sample. And the channel count is over
channels that collect their own reviews, because an aggregator carrying somebody
else content is not a second source.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from tariffpeg.dedupe.syndication import DEFAULT_RULES, SyndicationRules, group
from tariffpeg.model.channel import Channel
from tariffpeg.model.period import Season, StayMonth
from tariffpeg.model.review import Review
from tariffpeg.sample.regime import Requirement


@dataclass(frozen=True, slots=True)
class SeasonCoverage:
    """What is held against what is wanted, for one season."""

    season: Season
    wanted: int
    held: int

    @property
    def shortfall(self) -> int:
        """Return how many more are needed, which is never negative."""
        return max(0, self.wanted - self.held)

    @property
    def satisfied(self) -> bool:
        """Return whether this season has enough in it."""
        return self.held >= self.wanted


@dataclass(frozen=True, slots=True)
class Coverage:
    """What the unit holds for one licence, measured against the regime."""

    serial: int
    seasons: tuple[SeasonCoverage, ...]
    channels_held: tuple[str, ...]
    channels_wanted: int
    window: tuple[StayMonth, StayMonth]
    opinions: int

    def season(self, season: Season) -> SeasonCoverage:
        """Return the coverage for one season."""
        for entry in self.seasons:
            if entry.season is season:
                return entry
        return SeasonCoverage(season, 0, 0)

    @property
    def total_shortfall(self) -> int:
        """Return how many more reviews are needed across every season."""
        return sum(entry.shortfall for entry in self.seasons)

    @property
    def channel_shortfall(self) -> int:
        """Return how many more independent channels are needed."""
        return max(0, self.channels_wanted - len(self.channels_held))

    @property
    def satisfied(self) -> bool:
        """Return whether the licence is properly sampled."""
        return self.total_shortfall == 0 and self.channel_shortfall == 0

    def short_seasons(self) -> tuple[Season, ...]:
        """Return the seasons that still need reviews, worst first."""
        short = [entry for entry in self.seasons if entry.shortfall]
        short.sort(key=lambda entry: (-entry.shortfall, entry.season))
        return tuple(entry.season for entry in short)

    def statement(self) -> tuple[str, ...]:
        """Return the coverage statement a case file carries."""
        lines = [
            f"window {self.window[0]} to {self.window[1]}",
            f"{self.opinions} distinct opinions held",
        ]
        for entry in self.seasons:
            state = "met" if entry.satisfied else f"{entry.shortfall} short"
            lines.append(f"{entry.season}: {entry.held} of {entry.wanted} wanted, {state}")
        held = ", ".join(self.channels_held) if self.channels_held else "none"
        lines.append(f"independent channels: {held}, {self.channels_wanted} wanted")
        return tuple(lines)


def window_for(requirement: Requirement, at: StayMonth) -> tuple[StayMonth, StayMonth]:
    """Return the range of stay months the regime looks back over."""
    return at.minus(requirement.lookback_months - 1), at


def measure(
    requirement: Requirement,
    reviews: Sequence[Review],
    channels: Mapping[str, Channel],
    at: StayMonth,
    rules: SyndicationRules = DEFAULT_RULES,
) -> Coverage:
    """Measure what is held against what the regime asks for."""
    start, end = window_for(requirement, at)
    inside = [
        review
        for review in reviews
        if review.licence_serial == requirement.serial and start <= review.stay <= end
    ]
    clusters = group(inside, channels, rules)
    tally: dict[Season, int] = dict.fromkeys(Season, 0)
    independent: set[str] = set()
    for cluster in clusters:
        tally[cluster.leader.season()] += 1
        independent.update(cluster.independent_channels(channels))
    seasons = tuple(
        SeasonCoverage(season, requirement.wanted(season), tally[season]) for season in Season
    )
    return Coverage(
        serial=requirement.serial,
        seasons=seasons,
        channels_held=tuple(sorted(independent)),
        channels_wanted=requirement.minimum_channels,
        window=(start, end),
        opinions=len(clusters),
    )
