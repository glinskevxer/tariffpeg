"""Turning weighed contradictions into findings, one per particular.

The count that matters is voices, not contradictions. Four copies of one guest
syndicated across four channels is one voice. Two guests on the same channel is
two voices but only one channel, which is worth less than two guests on two
channels, because a channel with a broken template or a grudge is one point of
failure.

A single voice is deliberately worth less than it says on its face. One guest
can be wrong, can be describing the wrong property, or can have stayed in the
building next door. That is not a reason to ignore them. It is a reason not to
send an inspector on their word alone.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from tariffpeg.dedupe.syndication import DEFAULT_RULES, SyndicationRules, group
from tariffpeg.model.channel import Channel
from tariffpeg.model.licence import Licence
from tariffpeg.model.particulars import spec_for
from tariffpeg.model.review import Review
from tariffpeg.triage.weight import Weighed

CORROBORATION = {0: 0.0, 1: 0.6, 2: 1.0, 3: 1.25}
"""What a number of voices multiplies the weight by. Anything above the highest
key here uses the last entry plus a little, see :func:`corroboration_for`."""

MANY_VOICES = 1.4
"""What four or more voices multiply by."""

SPREAD_BONUS = 1.15
"""What is added when the voices come from more than one independent channel."""


def corroboration_for(voices: int, channels: int) -> float:
    """Return the multiplier for a number of voices across a number of channels."""
    base = CORROBORATION.get(voices, MANY_VOICES)
    if voices and channels > 1:
        base *= SPREAD_BONUS
    return round(base, 4)


@dataclass(frozen=True, slots=True)
class Finding:
    """Everything the unit holds against one particular of one licence."""

    licence_serial: int
    claim_key: str
    declared: str
    weighed: tuple[Weighed, ...]
    voices: int
    channels: tuple[str, ...]

    @property
    def raw_weight(self) -> float:
        """Return the weight before corroboration is taken into account."""
        return round(sum(item.weight for item in self.weighed), 4)

    @property
    def corroboration(self) -> float:
        """Return the multiplier the voices earn."""
        return corroboration_for(self.voices, len(self.channels))

    @property
    def score(self) -> float:
        """Return what this finding is worth."""
        return round(self.raw_weight * self.corroboration, 4)

    @property
    def structural_voices(self) -> int:
        """Return how many of the contradictions describe a feature."""
        return sum(1 for item in self.weighed if item.structural)

    def heaviest(self) -> Weighed | None:
        """Return the contradiction a case file leads with."""
        return self.weighed[0] if self.weighed else None

    def line(self) -> str:
        """Return the one line a case file prints for this finding."""
        spec = spec_for(self.claim_key)
        channels = ", ".join(self.channels) if self.channels else "no independent channel"
        return (
            f"{self.claim_key} ({spec.label}): {self.score:.2f}"
            f" from {self.voices} voices on {channels}"
        )


def build(
    weighed: Sequence[Weighed],
    reviews: Mapping[str, Review],
    channels: Mapping[str, Channel],
    licence: Licence,
    rules: SyndicationRules = DEFAULT_RULES,
) -> tuple[Finding, ...]:
    """Return one finding per particular, heaviest first."""
    by_claim: dict[str, list[Weighed]] = {}
    for item in weighed:
        by_claim.setdefault(item.claim_key, []).append(item)
    findings: list[Finding] = []
    for claim_key, items in by_claim.items():
        behind = [reviews[item.review_key] for item in items if item.review_key in reviews]
        clusters = group(behind, channels, rules)
        independent: set[str] = set()
        for cluster in clusters:
            independent.update(cluster.independent_channels(channels))
        ordered = tuple(sorted(items, key=lambda item: (-item.weight, item.review_key)))
        findings.append(
            Finding(
                licence_serial=licence.serial,
                claim_key=claim_key,
                declared=spec_for(claim_key).render(licence.particular(claim_key)),
                weighed=ordered,
                voices=len(clusters),
                channels=tuple(sorted(independent)),
            )
        )
    findings.sort(key=lambda finding: (-finding.score, finding.claim_key))
    return tuple(findings)
