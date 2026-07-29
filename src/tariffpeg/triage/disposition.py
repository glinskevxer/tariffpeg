"""What the unit does about a licence, once the evidence has been weighed.

Two rules here are not about weight at all and both of them decide cases.

An incomplete sample caps the disposition. However heavy the evidence looks, a
licence the unit has not properly sampled cannot be sent an inspector on the
strength of it, because the operator will ask what else was looked at and the
answer has to be more than nothing. The cap is a desk enquiry, which is the
step that goes and gets the rest of the sample.

Access particulars escalate. A missing lift or a step at the door is not the
same kind of finding as breakfast being charged for, and the order treats it as
its own category rather than as a heavier version of the same thing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from tariffpeg.errors import Invalid
from tariffpeg.model.outcome import SENDS_SOMEBODY_OUT, Disposition, heavier, rank
from tariffpeg.sample.coverage import Coverage
from tariffpeg.triage.corroborate import Finding

ACCESS_CLAIMS = frozenset({"lift", "step_free_entrance", "en_suite_all"})
"""Particulars a guest cannot work around and the order treats on their own."""

TAIL_SHARE = 0.5
"""What findings below the heaviest one contribute. One strong finding is worth
more than four weak ones adding up to the same number, because four weak ones
are four different things and none of them is worth a visit."""


@dataclass(frozen=True, slots=True)
class Thresholds:
    """Where the published bands sit."""

    desk: float = 3.0
    reinspection: float = 7.0
    urgent: float = 14.0
    access_reinspection: float = 5.0
    access_urgent: float = 9.0

    def __post_init__(self) -> None:
        if not 0 < self.desk < self.reinspection < self.urgent:
            raise Invalid("thresholds", self.desk, "the bands climb from nought in order")
        if not 0 < self.access_reinspection < self.access_urgent:
            raise Invalid(
                "access_reinspection",
                self.access_reinspection,
                "the access bands climb from nought in order",
            )

    def band(self, score: float) -> Disposition:
        """Return the band an ordinary score falls in."""
        if score >= self.urgent:
            return Disposition.URGENT
        if score >= self.reinspection:
            return Disposition.REINSPECTION
        if score >= self.desk:
            return Disposition.DESK_ENQUIRY
        return Disposition.NO_ACTION

    def access_band(self, score: float) -> Disposition:
        """Return the band an access score falls in."""
        if score >= self.access_urgent:
            return Disposition.URGENT
        if score >= self.access_reinspection:
            return Disposition.REINSPECTION
        return Disposition.NO_ACTION


PUBLISHED = Thresholds()
"""The bands in force."""


@dataclass(frozen=True, slots=True)
class Decision:
    """What the unit has decided about one licence, and why."""

    licence_serial: int
    disposition: Disposition
    score: float
    access_score: float
    findings: tuple[Finding, ...]
    reasons: tuple[str, ...]
    capped: bool = False

    @property
    def needs_a_visit(self) -> bool:
        """Return whether an inspector has to go out."""
        return self.disposition in SENDS_SOMEBODY_OUT

    def leading(self) -> Finding | None:
        """Return the finding the case file leads with."""
        return self.findings[0] if self.findings else None


def combine(findings: Sequence[Finding]) -> float:
    """Return the score for a set of findings."""
    if not findings:
        return 0.0
    scores = sorted((finding.score for finding in findings), reverse=True)
    return round(scores[0] + TAIL_SHARE * sum(scores[1:]), 4)


def decide(
    licence_serial: int,
    findings: Sequence[Finding],
    coverage: Coverage | None = None,
    thresholds: Thresholds = PUBLISHED,
) -> Decision:
    """Return what the unit does about a licence."""
    ordered = tuple(sorted(findings, key=lambda finding: (-finding.score, finding.claim_key)))
    score = combine(ordered)
    access = combine([finding for finding in ordered if finding.claim_key in ACCESS_CLAIMS])
    reasons: list[str] = []
    disposition = thresholds.band(score)
    reasons.append(f"the evidence scores {score:.2f}, which is a {disposition}")
    access_band = thresholds.access_band(access)
    if access_band is not Disposition.NO_ACTION:
        reasons.append(f"access findings score {access:.2f}, which is a {access_band}")
        disposition = heavier(disposition, access_band)
    capped = False
    short = coverage is not None and not coverage.satisfied
    if short and rank(disposition) > rank(Disposition.DESK_ENQUIRY):
        assert coverage is not None
        capped = True
        reasons.append(
            f"held at a desk enquiry because the sample is short by"
            f" {coverage.total_shortfall} reviews and"
            f" {coverage.channel_shortfall} channels"
        )
        disposition = Disposition.DESK_ENQUIRY
    return Decision(licence_serial, disposition, score, access, ordered, tuple(reasons), capped)
