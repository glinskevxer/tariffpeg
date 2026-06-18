"""The same figures, broken down by where the premises are.

The committee sits by ward and reads by ward. A locality where nothing is
properly sampled is a locality where nobody has been able to do the work, and
that is a resourcing conversation rather than a standards one, so it is worth
being able to see the two apart.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from tariffpeg.model.licence import Licence, LicenceStatus
from tariffpeg.report.rows import Column
from tariffpeg.sample.coverage import Coverage
from tariffpeg.triage.disposition import Decision, Disposition

COLUMNS = (
    Column("locality", "locality"),
    Column("licences", "licences", numeric=True),
    Column("sampled", "sampled", numeric=True),
    Column("short", "short", numeric=True),
    Column("visits", "needing a visit", numeric=True),
    Column("worst", "worst disposition"),
)
"""How the breakdown prints."""


@dataclass(frozen=True, slots=True)
class Place:
    """One locality, as the committee reads it."""

    locality: str
    licences: int
    sampled: int
    short: int
    needing_a_visit: int
    worst: Disposition

    @property
    def nothing_sampled(self) -> bool:
        """Return whether not one premises here has been properly sampled."""
        return self.licences > 0 and self.sampled == 0

    def row(self) -> dict[str, object]:
        """Return the row the breakdown prints."""
        return {
            "locality": self.locality,
            "licences": self.licences,
            "sampled": self.sampled,
            "short": self.short,
            "visits": self.needing_a_visit,
            "worst": str(self.worst),
        }


def _worst(found: Sequence[Decision]) -> Disposition:
    order = list(Disposition)
    worst = Disposition.NO_ACTION
    for decision in found:
        if order.index(decision.disposition) > order.index(worst):
            worst = decision.disposition
    return worst


def by_locality(
    licences: Sequence[Licence],
    coverages: Mapping[int, Coverage],
    decisions: Sequence[Decision],
) -> tuple[Place, ...]:
    """Return one entry per locality, in alphabetical order."""
    by_serial = {decision.licence_serial: decision for decision in decisions}
    grouped: dict[str, list[Licence]] = {}
    for licence in licences:
        if licence.status is LicenceStatus.ACTIVE:
            grouped.setdefault(licence.locality, []).append(licence)
    places: list[Place] = []
    for locality, held in sorted(grouped.items()):
        measured = [coverages[item.serial] for item in held if item.serial in coverages]
        found = [by_serial[item.serial] for item in held if item.serial in by_serial]
        places.append(
            Place(
                locality=locality,
                licences=len(held),
                sampled=sum(1 for coverage in measured if coverage.satisfied),
                short=sum(1 for coverage in measured if not coverage.satisfied),
                needing_a_visit=sum(1 for decision in found if decision.needs_a_visit),
                worst=_worst(found),
            )
        )
    return tuple(places)


def unsampled(places: Sequence[Place]) -> tuple[str, ...]:
    """Return the localities where nothing has been properly sampled."""
    return tuple(place.locality for place in places if place.nothing_sampled)
