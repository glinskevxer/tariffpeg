"""A notice from an operator saying they have put something right.

This is the operator side of the file and it changes what the evidence adds up
to. Once a notice is accepted for a particular, everything a guest said about
that particular before the work was done counts for very little, and everything
said after it counts in full.

The date that matters is not the date on the notice. It is the month the work
finished, because that is the month after which a guest could have seen the
difference. An operator cannot backdate that indefinitely, so there is a limit.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, replace

from tariffpeg.errors import Invalid
from tariffpeg.model.particulars import spec_for
from tariffpeg.model.period import StayMonth

BACKDATE_MONTHS = 12
"""How far before the filing the work is allowed to have finished."""


@dataclass(frozen=True, slots=True)
class Remediation:
    """One notice, against one particular of one licence."""

    licence_serial: int
    claim_key: str
    reference: str
    filed_on: dt.date
    effective_from: StayMonth
    accepted: bool = False
    note: str = ""

    def __post_init__(self) -> None:
        if self.licence_serial < 0:
            raise Invalid("licence_serial", self.licence_serial, "a serial is not negative")
        spec_for(self.claim_key)
        if not self.reference.strip():
            raise Invalid(
                "reference", self.reference, "a notice carries the number it was filed under"
            )
        filed_month = StayMonth.of(self.filed_on)
        if self.effective_from > filed_month:
            raise Invalid(
                "effective_from",
                str(self.effective_from),
                "the work cannot have finished after the notice was filed",
            )
        if filed_month.months_since(self.effective_from) > BACKDATE_MONTHS:
            raise Invalid(
                "effective_from",
                str(self.effective_from),
                f"a notice cannot reach back more than {BACKDATE_MONTHS} months",
            )

    @property
    def key(self) -> str:
        """Return the key the store holds this notice under."""
        return f"{self.licence_serial}:{self.claim_key}:{self.reference}"

    def covers(self, stay: StayMonth) -> bool:
        """Return whether a stay happened after the work was done."""
        return stay >= self.effective_from

    def accept(self, note: str = "") -> Remediation:
        """Return a copy the unit has accepted."""
        return replace(self, accepted=True, note=note or self.note)

    def refuse(self, why: str) -> Remediation:
        """Return a copy the unit has refused, with the reason on it."""
        if not why.strip():
            raise Invalid("note", why, "a refused notice says why it was refused")
        return replace(self, accepted=False, note=why)
