"""Which page on which channel is which licensed premises.

Nothing else in this package guesses. A harvest never searches a channel for a
trading name, because two guesthouses on one street share a name often enough
that the unit would end up quoting one operator against another. A listing is
recorded by hand, confirmed against the address, and reconfirmed when it goes
stale.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, replace

from tariffpeg.errors import Invalid
from tariffpeg.ids import is_slug
from tariffpeg.model.channel import Channel

CONFIRMATION_MONTHS = 18
"""How long a confirmation stands before somebody looks at the page again."""


@dataclass(frozen=True, slots=True)
class Listing:
    """One licensed premises as one channel lists it."""

    licence_serial: int
    channel: str
    path: str
    property_ref: str
    confirmed_on: dt.date
    active: bool = True
    note: str = ""

    def __post_init__(self) -> None:
        if self.licence_serial < 0:
            raise Invalid("licence_serial", self.licence_serial, "a serial is not negative")
        if not is_slug(self.channel):
            raise Invalid("channel", self.channel, "a listing belongs to a channel slug")
        if not self.path.startswith("/"):
            raise Invalid("path", self.path, "a listing path starts at the root of the channel")
        if self.path.endswith("/") and self.path != "/":
            raise Invalid("path", self.path, "a listing path carries no trailing slash")
        if not self.property_ref.strip():
            raise Invalid("property_ref", self.property_ref, "the channel numbers this property")

    @property
    def key(self) -> str:
        """Return the key the store holds this listing under."""
        return f"{self.licence_serial}:{self.channel}"

    def url(self, channel: Channel) -> str:
        """Return the address of this listing on its channel."""
        if channel.slug != self.channel:
            raise Invalid("channel", channel.slug, "this listing is on a different channel")
        return f"{channel.base_url}{self.path}"

    def stale_on(self, day: dt.date) -> bool:
        """Return whether the confirmation has gone stale by a given day."""
        months = (day.year - self.confirmed_on.year) * 12 + (day.month - self.confirmed_on.month)
        if day.day < self.confirmed_on.day:
            months -= 1
        return months >= CONFIRMATION_MONTHS

    def confirmed(self, day: dt.date) -> Listing:
        """Return a copy confirmed afresh on a given day."""
        return replace(self, confirmed_on=day)

    def retired(self, why: str) -> Listing:
        """Return a copy marked as no longer worth fetching."""
        if not why.strip():
            raise Invalid("note", why, "a retired listing says why it was retired")
        return replace(self, active=False, note=why)
