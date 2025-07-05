"""How many reviews the unit has to hold before a licence is properly sampled.

The regime is the thing that drives everything upstream of it. A harvest does
not go and fetch whatever it can reach, it goes and fetches what the regime says
is missing, which is why the shortfall is computed before the crawl budget is
spent rather than after.

Three things move the number. The grading band, because more is claimed of a
five key house than a two key one. The size of the premises, because eight
reviews of a forty room hotel is not a sample. And the closed season, because a
premises that shuts from November to March cannot produce off season reviews and
demanding them would leave every such licence permanently short.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field

from tariffpeg.errors import Invalid
from tariffpeg.model.licence import Licence
from tariffpeg.model.period import DEFAULT_SEASONS, Season, SeasonCalendar

BAND_FACTOR = {1: 1.0, 2: 1.0, 3: 1.5, 4: 2.0, 5: 2.5}
"""What the grading band multiplies the base quota by."""

ROOMS_PER_STEP = 10
"""Every this many let rooms adds one to the size multiplier."""


@dataclass(frozen=True, slots=True)
class Requirement:
    """What the regime asks of one licence for one period."""

    serial: int
    per_season: Mapping[Season, int]
    minimum_channels: int
    lookback_months: int

    @property
    def total(self) -> int:
        """Return how many reviews are wanted across the whole year."""
        return sum(self.per_season.values())

    def wanted(self, season: Season) -> int:
        """Return how many reviews are wanted in one season."""
        return self.per_season.get(season, 0)

    def explain(self) -> tuple[str, ...]:
        """Return one line per season, for the case file."""
        lines = []
        for season in Season:
            wanted = self.wanted(season)
            if wanted:
                lines.append(f"{season}: {wanted} reviews")
            else:
                lines.append(f"{season}: none, the premises is shut")
        lines.append(f"across at least {self.minimum_channels} channels")
        return tuple(lines)


@dataclass(frozen=True, slots=True)
class Regime:
    """The published sampling regime."""

    version: int
    base: Mapping[Season, int] = field(
        default_factory=lambda: {Season.PEAK: 8, Season.SHOULDER: 5, Season.OFF: 3}
    )
    calendar: SeasonCalendar = DEFAULT_SEASONS
    minimum_channels: int = 2
    lookback_months: int = 24

    def __post_init__(self) -> None:
        if self.version < 1:
            raise Invalid("version", self.version, "regime versions start at one")
        for season in Season:
            if season not in self.base:
                raise Invalid("base", str(season), "the regime sets a quota for every season")
            if self.base[season] < 0:
                raise Invalid("base", self.base[season], "a quota is not negative")
        if self.minimum_channels < 1:
            raise Invalid("minimum_channels", self.minimum_channels, "a sample needs one channel")
        if self.lookback_months < 1:
            raise Invalid("lookback_months", self.lookback_months, "a lookback is a month or more")

    def size_factor(self, let_rooms: int) -> int:
        """Return the multiplier the size of the premises adds."""
        if let_rooms < 1:
            raise Invalid("let_rooms", let_rooms, "a licensed premises lets at least one room")
        return 1 + (let_rooms - 1) // ROOMS_PER_STEP

    def band_factor(self, band: int) -> float:
        """Return the multiplier the grading band adds."""
        try:
            return BAND_FACTOR[band]
        except KeyError:
            raise Invalid("band", band, "the regime has no factor for this band") from None

    def open_share(self, licence: Licence, season: Season) -> float:
        """Return the fraction of a season the premises is open for."""
        months = self.calendar.months_in(season)
        if not months:
            return 0.0
        open_months = [month for month in months if not licence.is_closed_in(month)]
        return len(open_months) / len(months)

    def wanted(self, licence: Licence, season: Season) -> int:
        """Return how many reviews the regime wants in one season for a licence."""
        share = self.open_share(licence, season)
        if share == 0:
            return 0
        rooms = licence.particular("let_rooms")
        assert isinstance(rooms, int)
        raw = self.base[season] * self.band_factor(licence.band()) * self.size_factor(rooms) * share
        return math.ceil(raw)

    def require(self, licence: Licence) -> Requirement:
        """Return the whole requirement for a licence."""
        return Requirement(
            serial=licence.serial,
            per_season={season: self.wanted(licence, season) for season in Season},
            minimum_channels=self.minimum_channels,
            lookback_months=self.lookback_months,
        )


PUBLISHED = Regime(1)
"""The regime in force. A case file cites the version."""
