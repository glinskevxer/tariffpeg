"""Deciding when two reviews are one review, and grouping the copies.

This matters twice over. A syndicated copy must not count twice towards the
statutory sample, and it must not count as a second independent voice when a
contradiction is being corroborated. The second one is the dangerous half: two
copies of one guest saying the lift was out is one guest, and treating it as two
is how a re-inspection gets scheduled on the strength of nothing.

Three verdicts rather than two, because the middle one is real. Two primary
channels carrying the same words is usually a guest who pasted their own review
twice. That is one voice for corroboration and one entry in the sample, but it
is not the same record, so it is not called the same record.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from tariffpeg.dedupe.shingle import Signature
from tariffpeg.errors import Invalid
from tariffpeg.model.channel import Channel, SyndicationClass
from tariffpeg.model.review import Review


class Verdict(StrEnum):
    """What the comparison made of a pair."""

    SAME = "same"
    LIKELY = "likely"
    DIFFERENT = "different"


@dataclass(frozen=True, slots=True)
class SyndicationRules:
    """The thresholds the unit published for calling two reviews one."""

    same_threshold: float = 0.82
    likely_threshold: float = 0.58
    score_tolerance: int = 8
    month_tolerance: int = 0

    def __post_init__(self) -> None:
        if not 0 < self.likely_threshold <= self.same_threshold <= 1:
            raise Invalid(
                "same_threshold",
                self.same_threshold,
                "the thresholds climb from nought to one in order",
            )
        if self.score_tolerance < 0:
            raise Invalid("score_tolerance", self.score_tolerance, "a tolerance is not negative")
        if self.month_tolerance < 0:
            raise Invalid("month_tolerance", self.month_tolerance, "a tolerance is not negative")


DEFAULT_RULES = SyndicationRules()
"""The published thresholds."""


def compare(
    left: Review,
    right: Review,
    channels: Mapping[str, Channel],
    rules: SyndicationRules = DEFAULT_RULES,
) -> Verdict:
    """Return what the rules make of one pair of reviews."""
    if left.key == right.key:
        return Verdict.SAME
    if left.licence_serial != right.licence_serial:
        return Verdict.DIFFERENT
    if abs(left.stay.months_since(right.stay)) > rules.month_tolerance:
        return Verdict.DIFFERENT
    overlap = Signature.of(left.body).similarity(Signature.of(right.body))
    if overlap < rules.likely_threshold:
        return Verdict.DIFFERENT
    if left.channel == right.channel:
        return Verdict.LIKELY
    if abs(left.unit_points - right.unit_points) > rules.score_tolerance:
        return Verdict.LIKELY
    if overlap < rules.same_threshold:
        return Verdict.LIKELY
    if _either_reproduces(left, right, channels):
        return Verdict.SAME
    return Verdict.LIKELY


def _either_reproduces(left: Review, right: Review, channels: Mapping[str, Channel]) -> bool:
    reproducing = (SyndicationClass.AGGREGATOR, SyndicationClass.MIRROR)
    for review in (left, right):
        channel = channels.get(review.channel)
        if channel is not None and channel.syndication in reproducing:
            return True
    return False


@dataclass(frozen=True, slots=True)
class Cluster:
    """One opinion, and every copy of it the unit holds."""

    members: tuple[Review, ...]

    def __post_init__(self) -> None:
        if not self.members:
            raise Invalid("members", 0, "a cluster holds at least one review")

    @property
    def leader(self) -> Review:
        """Return the copy a case file quotes from.

        The earliest one the unit holds by store key, which is stable, rather
        than the longest or the highest scoring, which are not.
        """
        return self.members[0]

    @property
    def size(self) -> int:
        """Return how many copies are in this cluster."""
        return len(self.members)

    def channels(self) -> tuple[str, ...]:
        """Return the channels this opinion was found on."""
        return tuple(sorted({review.channel for review in self.members}))

    def independent_channels(self, channels: Mapping[str, Channel]) -> tuple[str, ...]:
        """Return the channels in this cluster that collect their own reviews."""
        return tuple(
            slug
            for slug in self.channels()
            if slug in channels and channels[slug].carries_own_reviews
        )

    def is_syndicated(self) -> bool:
        """Return whether this opinion turned up on more than one channel."""
        return len(self.channels()) > 1


def group(
    reviews: Sequence[Review],
    channels: Mapping[str, Channel],
    rules: SyndicationRules = DEFAULT_RULES,
) -> tuple[Cluster, ...]:
    """Group reviews so that each cluster is one opinion.

    Comparison is transitive here by construction, which is a simplification and
    a deliberate one. Three copies where the first and third fall just under the
    threshold are still one opinion, and splitting them would count that guest
    twice.
    """
    ordered = sorted(reviews, key=lambda review: review.key)
    parent = list(range(len(ordered)))

    def root(at: int) -> int:
        while parent[at] != at:
            parent[at] = parent[parent[at]]
            at = parent[at]
        return at

    for first in range(len(ordered)):
        for second in range(first + 1, len(ordered)):
            if compare(ordered[first], ordered[second], channels, rules) is Verdict.DIFFERENT:
                continue
            one, two = root(first), root(second)
            if one != two:
                parent[max(one, two)] = min(one, two)

    buckets: dict[int, list[Review]] = {}
    for index, review in enumerate(ordered):
        buckets.setdefault(root(index), []).append(review)
    return tuple(Cluster(tuple(members)) for _, members in sorted(buckets.items()))
