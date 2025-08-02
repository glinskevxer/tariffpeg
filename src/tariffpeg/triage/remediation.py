"""Discounting evidence an accepted remediation notice has answered.

The rule reads simply and it is the one operators care about most, so it is
worth being exact about. Once a notice is accepted for a particular, a guest who
stayed before the work counts for a fraction, and a guest who stayed after it
counts in full. A particular where every guest stayed before the work is
cleared, and clearing is not the same as having no evidence: a cleared
particular stays in the case file with its evidence attached and its weight
reduced, because if the same thing turns up again next season the file wants to
show that it has been here before.

An unaccepted notice discounts nothing. Filing a piece of paper is not doing the
work.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from tariffpeg.model.remediation import Remediation
from tariffpeg.triage.weight import PLACES, Weighed

BEFORE_THE_WORK = {True: 0.2, False: 0.05}
"""What a contradiction from before the work is still worth, by whether it
describes a feature. A structural report keeps more because it is a report about
the thing that was fixed, and a transient one keeps almost nothing because it
was a report about a week that has been overtaken."""


@dataclass(frozen=True, slots=True)
class Discount:
    """One contradiction, and what a notice did to its weight."""

    review_key: str
    claim_key: str
    reference: str
    factor: float
    was: float
    now: float

    def line(self) -> str:
        """Return the line the case file prints next to the discounted evidence."""
        return (
            f"{self.review_key} on {self.claim_key} cut from {self.was:.2f}"
            f" to {self.now:.2f} by {self.reference}"
        )


@dataclass(frozen=True, slots=True)
class Applied:
    """The evidence after the notices have been taken into account."""

    weighed: tuple[Weighed, ...]
    discounts: tuple[Discount, ...]
    cleared: tuple[str, ...]

    def for_claim(self, claim_key: str) -> tuple[Weighed, ...]:
        """Return the discounted evidence for one particular."""
        return tuple(item for item in self.weighed if item.claim_key == claim_key)

    def is_cleared(self, claim_key: str) -> bool:
        """Return whether every voice on this particular predates the work."""
        return claim_key in self.cleared


def apply(
    weighed: Sequence[Weighed],
    notices: Mapping[str, Remediation],
) -> Applied:
    """Return the evidence with accepted notices taken into account."""
    kept: list[Weighed] = []
    discounts: list[Discount] = []
    touched: dict[str, list[bool]] = {}
    for item in weighed:
        notice = notices.get(item.claim_key)
        if notice is None or not notice.accepted:
            kept.append(item)
            continue
        after = notice.covers(item.contradiction.stay)
        touched.setdefault(item.claim_key, []).append(after)
        if after:
            kept.append(item)
            continue
        factor = BEFORE_THE_WORK[item.structural]
        reduced = round(item.weight * factor, PLACES)
        discounts.append(
            Discount(
                review_key=item.review_key,
                claim_key=item.claim_key,
                reference=notice.reference,
                factor=factor,
                was=item.weight,
                now=reduced,
            )
        )
        kept.append(replace(item, weight=reduced))
    cleared = tuple(sorted(claim for claim, marks in touched.items() if marks and not any(marks)))
    return Applied(tuple(kept), tuple(discounts), cleared)


def notices_by_claim(notices: Sequence[Remediation]) -> dict[str, Remediation]:
    """Return the notice that reaches furthest forward for each particular.

    Only accepted notices are considered. Two accepted notices for one
    particular means the work was done twice, and the later one is the one a
    guest could have seen.
    """
    latest: dict[str, Remediation] = {}
    for notice in notices:
        if not notice.accepted:
            continue
        held = latest.get(notice.claim_key)
        if held is None or notice.effective_from > held.effective_from:
            latest[notice.claim_key] = notice
    return latest
