"""The licence: an operator, a period, and the particulars they signed for.

A licence runs for a period and can be closed for part of the year. Both matter
to the harvest, because a review of a stay in a month the operator says they
were shut is either a mistake by the guest, a mistake by the channel, or the
most interesting thing in the file.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum

from tariffpeg.errors import Invalid, NotFound
from tariffpeg.ids import format_licence_ref
from tariffpeg.model.particulars import spec_for

MANDATORY_KEYS = ("grading_band", "let_rooms", "bed_spaces")
"""Particulars an application cannot be accepted without."""


class LicenceStatus(StrEnum):
    """Where a licence sits in its life."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    LAPSED = "lapsed"
    SURRENDERED = "surrendered"


@dataclass(frozen=True, slots=True)
class Licence:
    """One licensed premises as the register holds it."""

    serial: int
    trading_name: str
    operator_name: str
    locality: str
    period_start: dt.date
    period_end: dt.date
    particulars: Mapping[str, bool | int]
    closed_months: frozenset[int] = field(default_factory=frozenset)
    status: LicenceStatus = LicenceStatus.ACTIVE
    operator_ref: str = ""

    def __post_init__(self) -> None:
        if not self.trading_name.strip():
            raise Invalid("trading_name", self.trading_name, "a licence needs a trading name")
        if not self.operator_name.strip():
            raise Invalid("operator_name", self.operator_name, "a licence needs an operator")
        if self.period_end <= self.period_start:
            raise Invalid(
                "period_end",
                self.period_end.isoformat(),
                "a licence period ends after it starts",
            )
        for month in sorted(self.closed_months):
            if not 1 <= month <= 12:
                raise Invalid("closed_months", month, "a month runs from one to twelve")
        if len(self.closed_months) == 12:
            raise Invalid("closed_months", 12, "a premises closed all year is not trading")
        for key, value in self.particulars.items():
            spec_for(key).validate(value)
        for key in MANDATORY_KEYS:
            if key not in self.particulars:
                raise Invalid("particulars", key, "this particular is required on every licence")

    @property
    def ref(self) -> str:
        """Return the reference printed on the plaque in the hall."""
        return format_licence_ref(self.serial)

    def declares(self, key: str) -> bool:
        """Return whether this licence carries the named particular."""
        return key in self.particulars

    def particular(self, key: str) -> bool | int:
        """Return the value declared for a particular, or refuse."""
        spec_for(key)
        try:
            return self.particulars[key]
        except KeyError:
            raise NotFound("particular", f"{self.ref}/{key}") from None

    def band(self) -> int:
        """Return the awarded grading band in keys."""
        value = self.particular("grading_band")
        assert isinstance(value, int)
        return value

    def covers(self, day: dt.date) -> bool:
        """Return whether the day falls inside the licence period."""
        return self.period_start <= day <= self.period_end

    def is_closed_in(self, month: int) -> bool:
        """Return whether the operator declared this month a closed one."""
        if not 1 <= month <= 12:
            raise Invalid("month", month, "a month runs from one to twelve")
        return month in self.closed_months

    def is_trading_on(self, day: dt.date) -> bool:
        """Return whether guests could have stayed on this day.

        Suspended is not trading. Lapsed and surrendered are not trading. A
        closed month is not trading even while the licence is active, which is
        the case that puts a review in front of an inspector.
        """
        if self.status is not LicenceStatus.ACTIVE:
            return False
        if not self.covers(day):
            return False
        return not self.is_closed_in(day.month)

    def open_months(self) -> tuple[int, ...]:
        """Return the months the operator says they trade, in calendar order."""
        return tuple(m for m in range(1, 13) if m not in self.closed_months)

    def with_particular(self, key: str, value: bool | int) -> Licence:
        """Return a copy with one particular changed.

        The register is amended by variation, never in place, because the case
        file has to be able to say what was declared at the time of the stay.
        """
        spec_for(key).validate(value)
        merged = dict(self.particulars)
        merged[key] = value
        return replace(self, particulars=merged)

    def with_status(self, status: LicenceStatus) -> Licence:
        """Return a copy in a new status."""
        return replace(self, status=status)

    def with_operator(self, ref: str) -> Licence:
        """Return a copy tied to an operator on the register.

        The operator name stays on the licence as it was written when the
        licence was granted. The reference is what a letter follows, and the two
        are allowed to differ because operators change their trading style far
        more often than they change who they are.
        """
        return replace(self, operator_ref=ref)
