"""What the unit sent an operator, and whether they answered.

An operator who says they were never told is answered with this. It carries the
digest of what went out rather than the words, for the same reason a capture
does: the words are in the sent folder, and what the register needs is something
that proves the file has not been rewritten since.

The reply clock runs in working days from the day the letter went, and it is the
only clock in this package that does. Everything else works in months, because
everything else is about stays.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, replace
from enum import StrEnum

from tariffpeg.errors import Conflict, Invalid
from tariffpeg.ids import is_slug
from tariffpeg.workdays import add_working_days


class Sent(StrEnum):
    """What kind of letter went out."""

    DESK_ENQUIRY = "desk enquiry"
    NOTICE_OF_INSPECTION = "notice of inspection"
    OUTCOME = "outcome"
    REMINDER = "reminder"


REPLY_DAYS = {
    Sent.DESK_ENQUIRY: 14,
    Sent.NOTICE_OF_INSPECTION: 5,
    Sent.OUTCOME: 21,
    Sent.REMINDER: 7,
}
"""How many working days each kind gives an operator to answer."""


@dataclass(frozen=True, slots=True)
class Letter:
    """One letter, and whether it was answered."""

    reference: str
    operator_ref: str
    licence_serial: int
    kind: Sent
    sent_on: dt.date
    subject: str
    body_digest: str
    replied_on: dt.date | None = None

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise Invalid("reference", self.reference, "a letter carries the number it went under")
        if not is_slug(self.operator_ref):
            raise Invalid("operator_ref", self.operator_ref, "a letter goes to an operator")
        if self.licence_serial < 0:
            raise Invalid("licence_serial", self.licence_serial, "a serial is not negative")
        if not self.subject.strip():
            raise Invalid("subject", self.subject, "a letter says what it is about")
        if not self.body_digest.startswith("sha256:"):
            raise Invalid("body_digest", self.body_digest, "a letter carries the digest of itself")
        if self.replied_on is not None and self.replied_on < self.sent_on:
            raise Conflict("reply", "it is dated before the letter it answers")

    @property
    def key(self) -> str:
        """Return the key the store holds this letter under."""
        return self.reference

    @property
    def answered(self) -> bool:
        """Return whether the operator has replied."""
        return self.replied_on is not None

    def due_on(self, holidays: frozenset[dt.date] = frozenset()) -> dt.date:
        """Return the day a reply stops being on time."""
        return add_working_days(self.sent_on, REPLY_DAYS[self.kind], holidays)

    def overdue_on(self, day: dt.date, holidays: frozenset[dt.date] = frozenset()) -> bool:
        """Return whether a reply is late as at a given day."""
        if self.answered:
            return False
        return day > self.due_on(holidays)

    def answered_late(self, holidays: frozenset[dt.date] = frozenset()) -> bool:
        """Return whether the reply that came was later than it should have been."""
        if self.replied_on is None:
            return False
        return self.replied_on > self.due_on(holidays)

    def with_reply(self, day: dt.date) -> Letter:
        """Return a copy recording that the operator answered."""
        return replace(self, replied_on=day)
