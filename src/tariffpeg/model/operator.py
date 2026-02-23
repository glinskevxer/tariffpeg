"""The operator: who holds the licence, and where a letter goes.

One operator holds several licences often enough that the register keeps them
apart. It matters twice. A letter about one premises goes to the person who
holds it, not to the trading name on the door, and a pattern across three of
somebody premises is a different conversation from a pattern at one.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, replace

from tariffpeg.errors import Invalid
from tariffpeg.ids import is_slug

EMAIL = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]+$")


@dataclass(frozen=True, slots=True)
class Operator:
    """One operator as the register holds them."""

    ref: str
    name: str
    contact_name: str
    email: str
    address: str
    registered_on: dt.date
    note: str = ""

    def __post_init__(self) -> None:
        if not is_slug(self.ref):
            raise Invalid("ref", self.ref, "an operator reference is a slug")
        if not self.name.strip():
            raise Invalid("name", self.name, "an operator has a name on the licence")
        if not self.contact_name.strip():
            raise Invalid("contact_name", self.contact_name, "a letter is addressed to somebody")
        if not EMAIL.match(self.email.strip()):
            raise Invalid("email", self.email, "this is not an address a letter can go to")
        if not self.address.strip():
            raise Invalid("address", self.address, "an operator has an address on the register")

    def letter_to(self) -> str:
        """Return the line a letter is addressed to."""
        return f"{self.contact_name}, {self.name}"

    def with_contact(self, contact_name: str, email: str) -> Operator:
        """Return a copy with a new person to write to."""
        return replace(self, contact_name=contact_name, email=email)

    def with_address(self, address: str) -> Operator:
        """Return a copy at a new address."""
        return replace(self, address=address)

    def years_on_the_register(self, at: dt.date) -> int:
        """Return how many whole years this operator has been registered."""
        years = at.year - self.registered_on.year
        if (at.month, at.day) < (self.registered_on.month, self.registered_on.day):
            years -= 1
        return max(0, years)
