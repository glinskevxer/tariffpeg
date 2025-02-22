"""Booking channels and the terms on which this unit is willing to read them.

Every channel we harvest has been written to, and the reply is what a fetch
policy records. Two channels asked to be read outside their own trading peak,
which is the courtesy window. One publishes a crawl delay in its robots file
that is longer than the one it agreed with us, and the longer of the two wins.

None of this is negotiable at run time. A policy is data on the channel record,
so a change to it is a change an inspector can point at in the register.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum

from tariffpeg.errors import Invalid
from tariffpeg.ids import is_slug


class SyndicationClass(StrEnum):
    """Where a channel's reviews come from.

    A primary channel collects its own. An aggregator reproduces other people's
    under its own numbering. A mirror is the same operator's stock behind a
    different brand, so its reviews are the same records, not similar ones.
    """

    PRIMARY = "primary"
    AGGREGATOR = "aggregator"
    MIRROR = "mirror"


@dataclass(frozen=True, slots=True)
class CourtesyWindow:
    """The hours of the day a channel asked to be read in, in UTC.

    A window may wrap midnight, which is the usual case: the channels that ask
    for one are asking to be left alone during their own booking peak.
    """

    open_hour: int
    close_hour: int

    def __post_init__(self) -> None:
        for name, value in (("open_hour", self.open_hour), ("close_hour", self.close_hour)):
            if not 0 <= value <= 23:
                raise Invalid(name, value, "an hour of the day runs from zero to twenty three")
        if self.open_hour == self.close_hour:
            raise Invalid(
                "close_hour",
                self.close_hour,
                "a window that opens and closes on the same hour is not a window",
            )

    @property
    def wraps_midnight(self) -> bool:
        """Return whether the window runs across the end of the day."""
        return self.open_hour > self.close_hour

    def hours(self) -> tuple[int, ...]:
        """Return every hour the window is open, in clock order."""
        if self.wraps_midnight:
            return tuple(range(self.open_hour, 24)) + tuple(range(0, self.close_hour))
        return tuple(range(self.open_hour, self.close_hour))

    def is_open_at(self, instant: dt.datetime) -> bool:
        """Return whether the window is open at this instant."""
        return instant.hour in self.hours()

    def next_open(self, instant: dt.datetime) -> dt.datetime:
        """Return the first instant at or after this one that the window is open.

        The answer is on an hour boundary. A fetcher that has been told to wait
        is not asked to wait a fraction of an hour and then try again.
        """
        if self.is_open_at(instant):
            return instant
        candidate = instant.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
        for _ in range(25):
            if self.is_open_at(candidate):
                return candidate
            candidate += dt.timedelta(hours=1)
        raise AssertionError("a window with at least one open hour is reachable within a day")


ALWAYS = CourtesyWindow(0, 23)
"""The window for a channel that never asked for one. Twenty three of the
twenty four hours, because the hour before midnight is when the channels that
did ask are all asleep and we would rather not be the only traffic."""


@dataclass(frozen=True, slots=True)
class FetchPolicy:
    """What this unit agreed it would do when reading a channel."""

    user_agent: str
    crawl_delay_ms: int
    daily_request_ceiling: int
    window: CourtesyWindow = ALWAYS
    max_pages_per_property: int = 12

    def __post_init__(self) -> None:
        if "@" not in self.user_agent:
            raise Invalid(
                "user_agent",
                self.user_agent,
                "the agreed agent string carries a contact address",
            )
        if self.crawl_delay_ms < 250:
            raise Invalid("crawl_delay_ms", self.crawl_delay_ms, "the floor for any channel is 250")
        if self.daily_request_ceiling < 1:
            raise Invalid(
                "daily_request_ceiling",
                self.daily_request_ceiling,
                "a ceiling below one is a channel we are not reading",
            )
        if self.max_pages_per_property < 1:
            raise Invalid(
                "max_pages_per_property",
                self.max_pages_per_property,
                "a page limit below one is a channel we are not reading",
            )

    def delay_with(self, published_delay_ms: int | None) -> int:
        """Return the delay to use once the channel's own robots file is read.

        The longer of the two wins. A channel that publishes a delay shorter
        than the one it agreed with us has not shortened the agreement.
        """
        if published_delay_ms is None:
            return self.crawl_delay_ms
        return max(self.crawl_delay_ms, published_delay_ms)


@dataclass(frozen=True, slots=True)
class Channel:
    """A booking channel as the register holds it."""

    slug: str
    name: str
    base_url: str
    syndication: SyndicationClass
    policy: FetchPolicy
    locale: str = "en"

    def __post_init__(self) -> None:
        if not is_slug(self.slug):
            raise Invalid("slug", self.slug, "a channel slug is lowercase and hyphen separated")
        if not self.name.strip():
            raise Invalid("name", self.name, "a channel needs a name for the case file")
        if not self.base_url.startswith("https://"):
            raise Invalid("base_url", self.base_url, "channels are read over https only")
        if self.base_url.endswith("/"):
            raise Invalid("base_url", self.base_url, "the base url carries no trailing slash")

    @property
    def carries_own_reviews(self) -> bool:
        """Return whether a review found here was written here."""
        return self.syndication is SyndicationClass.PRIMARY
