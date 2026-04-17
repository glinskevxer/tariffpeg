"""The arithmetic behind one decision, written out.

The case file says what was decided. This says how the number was got to, in the
order it was got to, so that somebody who disagrees can point at the step they
disagree with rather than at the answer.

It is deliberately long. Everything in it is already in the case file somewhere,
and having it in one column with the multiplications shown is the difference
between a number an operator can argue with and a number they can only accept.
"""

from __future__ import annotations

from dataclasses import dataclass

from tariffpeg.model.particulars import spec_for
from tariffpeg.report.casefile import CaseFile
from tariffpeg.triage.corroborate import Finding
from tariffpeg.triage.disposition import ACCESS_CLAIMS, TAIL_SHARE, Disposition


@dataclass(frozen=True, slots=True)
class Explanation:
    """One decision, taken apart."""

    file: CaseFile

    def evidence(self) -> tuple[str, ...]:
        """Return what was found, one line per contradiction."""
        lines: list[str] = []
        for finding in self.file.decision.findings:
            spec = spec_for(finding.claim_key)
            lines.append(f"{finding.claim_key} ({spec.label}), declared {finding.declared}")
            for item in finding.weighed:
                lines.append(
                    f"  {item.review_key}: rule {item.contradiction.rule_id},"
                    f" strength {item.contradiction.strength},"
                    f" {item.months_old} months old,"
                    f" worth {item.weight:.2f}"
                )
        return tuple(lines)

    def discounts(self) -> tuple[str, ...]:
        """Return what an accepted notice did to the evidence."""
        if not self.file.applied.discounts:
            return ("no accepted notice has discounted anything",)
        return tuple(discount.line() for discount in self.file.applied.discounts)

    def corroboration(self) -> tuple[str, ...]:
        """Return how each finding was multiplied by the voices behind it."""
        return tuple(
            f"{finding.claim_key}: {finding.raw_weight:.2f} raw"
            f" times {finding.corroboration:.2f} for {finding.voices} voices"
            f" on {len(finding.channels)} independent channels"
            f" is {finding.score:.2f}"
            for finding in self.file.decision.findings
        )

    def arithmetic(self) -> tuple[str, ...]:
        """Return how the findings were added up into one score."""
        findings = self.file.decision.findings
        if not findings:
            return ("nothing was found, so the score is nought",)
        lines = [f"the heaviest finding is {findings[0].claim_key} at {findings[0].score:.2f}"]
        for finding in findings[1:]:
            lines.append(
                f"{finding.claim_key} adds {finding.score:.2f}"
                f" times {TAIL_SHARE:g} which is {finding.score * TAIL_SHARE:.2f}"
            )
        lines.append(f"the evidence scores {self.file.decision.score:.2f}")
        access = [f for f in findings if f.claim_key in ACCESS_CLAIMS]
        if access:
            names = ", ".join(finding.claim_key for finding in access)
            lines.append(
                f"the access findings ({names}) score"
                f" {self.file.decision.access_score:.2f} on their own"
            )
        return tuple(lines)

    def outcome(self) -> tuple[str, ...]:
        """Return what the score came to and what held it back."""
        lines = list(self.file.decision.reasons)
        if self.file.decision.capped:
            lines.append("the sample has to be completed before this can go further")
        elif self.file.decision.disposition is Disposition.NO_ACTION:
            lines.append("nothing here is heavy enough to act on")
        return tuple(lines)

    def lines(self) -> tuple[str, ...]:
        """Return the whole explanation."""
        blocks = (
            ("what was found", self.evidence()),
            ("what a notice discounted", self.discounts()),
            ("what the voices multiplied it by", self.corroboration()),
            ("how it was added up", self.arithmetic()),
            ("what came of it", self.outcome()),
        )
        out: list[str] = [
            f"{self.file.licence.ref}  {self.file.licence.trading_name}",
            f"decided at {self.file.decided_at}",
            "",
        ]
        for title, body in blocks:
            out.append(title.upper())
            out.extend(body if body else ("nothing",))
            out.append("")
        return tuple(out[:-1])


def explain(file: CaseFile) -> Explanation:
    """Return the arithmetic behind a case file."""
    return Explanation(file)


def heaviest(file: CaseFile) -> Finding | None:
    """Return the finding that decided the outcome, if there was one."""
    return file.decision.leading()
