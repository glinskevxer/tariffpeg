"""The case file: everything an inspector is handed before they go out.

Every quotation carries the digest of the bytes it was read out of and the
instant they were served. That is not decoration. An operator who says a
quotation is invented is answered by fetching the page again and comparing the
digest, and a quotation that cannot be answered for should not be in the file.

The last section says what would change the decision. It is there because the
decision is a judgement made from a number, and the operator is entitled to know
which way the number moves.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from tariffpeg.claims.contradiction import read_all
from tariffpeg.claims.rules import RulePack
from tariffpeg.model.capture import Capture
from tariffpeg.model.channel import Channel
from tariffpeg.model.licence import Licence
from tariffpeg.model.period import StayMonth
from tariffpeg.model.remediation import Remediation
from tariffpeg.model.review import Review
from tariffpeg.sample.coverage import Coverage
from tariffpeg.triage.corroborate import Finding
from tariffpeg.triage.corroborate import build as build_findings
from tariffpeg.triage.disposition import Decision, Disposition, Thresholds, decide
from tariffpeg.triage.remediation import Applied, apply, notices_by_claim
from tariffpeg.triage.schedule import Booking, Refusal
from tariffpeg.triage.weight import weigh_all


@dataclass(frozen=True, slots=True)
class Quotation:
    """One thing a guest said, with the paperwork that answers for it."""

    claim_key: str
    review_key: str
    channel: str
    stay: StayMonth
    quote: str
    capture_digest: str
    fetched_at: dt.datetime | None
    weight: float

    def line(self) -> str:
        """Return the quotation as the file prints it."""
        served = self.fetched_at.date().isoformat() if self.fetched_at else "not on file"
        return (
            f"  {self.stay} on {self.channel} ({self.weight:.2f}): {self.quote}"
            f" [{self.capture_digest[:19]}, served {served}]"
        )


@dataclass(frozen=True, slots=True)
class CaseFile:
    """One licence, one decision and the evidence behind it."""

    licence: Licence
    decided_at: StayMonth
    decision: Decision
    coverage: Coverage
    applied: Applied
    quotations: tuple[Quotation, ...]
    notices: tuple[Remediation, ...]
    visit: Booking | Refusal | None = None

    def quotations_for(self, claim_key: str) -> tuple[Quotation, ...]:
        """Return the quotations behind one finding."""
        return tuple(item for item in self.quotations if item.claim_key == claim_key)

    def heading(self) -> tuple[str, ...]:
        """Return the identity block."""
        return (
            f"{self.licence.ref}  {self.licence.trading_name}, {self.licence.locality}",
            f"operator {self.licence.operator_name}, {self.licence.band()} keys,"
            f" {self.licence.particular('let_rooms')} let rooms",
            f"decided at {self.decided_at}, disposition {self.decision.disposition}",
        )

    def findings_block(self) -> tuple[str, ...]:
        """Return the findings, each with the quotations behind it."""
        if not self.decision.findings:
            return ("nothing was found against the particulars on this licence",)
        lines: list[str] = []
        for finding in self.decision.findings:
            lines.append(finding.line())
            if self.applied.is_cleared(finding.claim_key):
                lines.append("  every voice on this predates an accepted remediation notice")
            lines.extend(item.line() for item in self.quotations_for(finding.claim_key))
        return tuple(lines)

    def remediation_block(self) -> tuple[str, ...]:
        """Return what the operator has filed and what it did."""
        if not self.notices:
            return ("no remediation notices are on file",)
        lines = [
            f"{notice.reference} on {notice.claim_key},"
            f" work finished {notice.effective_from},"
            f" {'accepted' if notice.accepted else 'not accepted'}"
            for notice in self.notices
        ]
        lines.extend(discount.line() for discount in self.applied.discounts)
        return tuple(lines)

    def visit_block(self) -> tuple[str, ...]:
        """Return what was booked, if anything."""
        if self.visit is None:
            return ("no visit was sought",)
        if isinstance(self.visit, Refusal):
            return (f"no visit was booked: {self.visit.reason}",)
        return (f"{self.visit.inspector} to visit on {self.visit.day}",)

    def what_would_change_this(self) -> tuple[str, ...]:
        """Return the lines saying which way the decision moves."""
        lines: list[str] = []
        if self.decision.capped:
            lines.append("completing the sample would let the evidence stand at its own weight")
        if self.decision.disposition is Disposition.NO_ACTION:
            lines.append("one more corroborating voice would raise this above no action")
        else:
            lines.append("an accepted remediation notice would discount the evidence before it")
        if self.coverage.channel_shortfall:
            lines.append(f"{self.coverage.channel_shortfall} more independent channels are wanted")
        return tuple(lines)

    def lines(self) -> tuple[str, ...]:
        """Return the whole file as text."""
        blocks = (
            ("identity", self.heading()),
            ("why", self.decision.reasons),
            ("sample", self.coverage.statement()),
            ("findings", self.findings_block()),
            ("remediation", self.remediation_block()),
            ("visit", self.visit_block()),
            ("what would change this", self.what_would_change_this()),
        )
        out: list[str] = []
        for title, body in blocks:
            out.append(title.upper())
            out.extend(body)
            out.append("")
        return tuple(out[:-1])


def build(
    licence: Licence,
    reviews: Sequence[Review],
    channels: Mapping[str, Channel],
    coverage: Coverage,
    notices: Sequence[Remediation],
    pack: RulePack,
    at: StayMonth,
    captures: Mapping[str, Capture] | None = None,
    thresholds: Thresholds | None = None,
    visit: Booking | Refusal | None = None,
) -> CaseFile:
    """Build a case file for one licence out of everything the store holds."""
    mine = [review for review in reviews if review.licence_serial == licence.serial]
    by_key = {review.key: review for review in mine}
    found = read_all(tuple(mine), licence, pack)
    weighed = weigh_all(found, at)
    applied = apply(weighed, notices_by_claim(notices))
    findings = build_findings(applied.weighed, by_key, channels, licence)
    decision = (
        decide(licence.serial, findings, coverage, thresholds)
        if thresholds is not None
        else decide(licence.serial, findings, coverage)
    )
    return CaseFile(
        licence=licence,
        decided_at=at,
        decision=decision,
        coverage=coverage,
        applied=applied,
        quotations=_quotations(findings, by_key, captures or {}),
        notices=tuple(sorted(notices, key=lambda notice: (notice.claim_key, notice.reference))),
        visit=visit,
    )


def _quotations(
    findings: Sequence[Finding],
    reviews: Mapping[str, Review],
    captures: Mapping[str, Capture],
) -> tuple[Quotation, ...]:
    out: list[Quotation] = []
    for finding in findings:
        for item in finding.weighed:
            review = reviews.get(item.review_key)
            if review is None:
                continue
            capture = captures.get(review.capture_digest)
            out.append(
                Quotation(
                    claim_key=finding.claim_key,
                    review_key=review.key,
                    channel=review.channel,
                    stay=review.stay,
                    quote=review.quote(),
                    capture_digest=review.capture_digest,
                    fetched_at=capture.fetched_at if capture else None,
                    weight=item.weight,
                )
            )
    return tuple(out)
