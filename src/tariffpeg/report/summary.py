"""The return the unit files every month.

It is one page and it is the same page every month, which is the point: a number
that moves is visible against eleven others that did not. The figure the
committee always asks about first is how many licences the unit could not decide
about because the sample was short, so that one is on its own line.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from tariffpeg.model.licence import Licence, LicenceStatus
from tariffpeg.model.period import StayMonth
from tariffpeg.report.rows import Column
from tariffpeg.sample.coverage import Coverage
from tariffpeg.triage.disposition import Decision, Disposition

COLUMNS = (
    Column("figure", "figure"),
    Column("count", "count", numeric=True),
)
"""How the return prints."""


@dataclass(frozen=True, slots=True)
class Return:
    """One month of the unit, as the committee reads it."""

    month: StayMonth
    on_the_register: int
    active: int
    sampled: int
    short: int
    held_back: int
    dispositions: Mapping[Disposition, int]
    opinions: int
    reviews_short: int

    @property
    def needing_a_visit(self) -> int:
        """Return how many licences need somebody sent out."""
        return self.dispositions.get(Disposition.REINSPECTION, 0) + self.dispositions.get(
            Disposition.URGENT, 0
        )

    def rows(self) -> tuple[dict[str, object], ...]:
        """Return the figures, in the order the return prints them."""
        listed: list[dict[str, object]] = [
            {"figure": "licences on the register", "count": self.on_the_register},
            {"figure": "of those, active", "count": self.active},
            {"figure": "properly sampled", "count": self.sampled},
            {"figure": "short of the sample", "count": self.short},
            {"figure": "reviews still wanted", "count": self.reviews_short},
            {"figure": "distinct opinions held", "count": self.opinions},
        ]
        listed.extend(
            {
                "figure": f"disposition, {disposition}",
                "count": self.dispositions.get(disposition, 0),
            }
            for disposition in Disposition
        )
        listed.append({"figure": "held back by a short sample", "count": self.held_back})
        listed.append({"figure": "needing a visit", "count": self.needing_a_visit})
        return tuple(listed)

    def lines(self) -> tuple[str, ...]:
        """Return the return as text."""
        return (
            f"Return for {self.month}",
            "",
            *(f"{row['figure']}: {row['count']}" for row in self.rows()),
        )


def compile_return(
    month: StayMonth,
    licences: Sequence[Licence],
    coverages: Mapping[int, Coverage],
    decisions: Sequence[Decision],
) -> Return:
    """Build the return for a month out of what the unit holds."""
    active = [licence for licence in licences if licence.status is LicenceStatus.ACTIVE]
    measured = [coverages[licence.serial] for licence in active if licence.serial in coverages]
    tally: dict[Disposition, int] = dict.fromkeys(Disposition, 0)
    for decision in decisions:
        tally[decision.disposition] += 1
    return Return(
        month=month,
        on_the_register=len(licences),
        active=len(active),
        sampled=sum(1 for coverage in measured if coverage.satisfied),
        short=sum(1 for coverage in measured if not coverage.satisfied),
        held_back=sum(1 for decision in decisions if decision.capped),
        dispositions=tally,
        opinions=sum(coverage.opinions for coverage in measured),
        reviews_short=sum(coverage.total_shortfall for coverage in measured),
    )
