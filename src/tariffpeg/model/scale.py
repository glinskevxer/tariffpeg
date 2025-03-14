"""Turning a channel's score into the unit's own hundred points.

This is not a rescale. Channels put words next to their numbers, and the words
are not spaced evenly. One channel calls eight out of ten "very good" and nine
"superb", and the gap between those two in a guest's head is nothing like the
gap between five and six on the same dial. The unit published a table of
anchors for each channel, agreed with the channel, and normalisation is a
straight line between whichever two anchors the score falls between.

Scores arrive as tenths throughout. A channel that grades in whole points is a
channel whose tenths all end in zero.
"""

from __future__ import annotations

from dataclasses import dataclass

from tariffpeg.errors import Invalid
from tariffpeg.ids import is_slug


@dataclass(frozen=True, slots=True)
class Anchor:
    """One agreed point on a channel's dial and what the unit calls it."""

    tenths: int
    unit_points: int
    label: str

    def __post_init__(self) -> None:
        if not 0 <= self.unit_points <= 100:
            raise Invalid("unit_points", self.unit_points, "the unit scale is nought to a hundred")
        if not self.label.strip():
            raise Invalid("label", self.label, "an anchor carries the channel's own word for it")


@dataclass(frozen=True, slots=True)
class ScoreScale:
    """A channel's dial, and the agreed table that maps it onto the unit's."""

    slug: str
    low_tenths: int
    high_tenths: int
    anchors: tuple[Anchor, ...]

    def __post_init__(self) -> None:
        if not is_slug(self.slug):
            raise Invalid("slug", self.slug, "a scale is named with a slug")
        if self.high_tenths <= self.low_tenths:
            raise Invalid("high_tenths", self.high_tenths, "the top of a dial is above its foot")
        if len(self.anchors) < 2:
            raise Invalid("anchors", len(self.anchors), "a table needs both ends at least")
        if self.anchors[0].tenths != self.low_tenths:
            raise Invalid("anchors", self.anchors[0].tenths, "the first anchor is the foot of dial")
        if self.anchors[-1].tenths != self.high_tenths:
            raise Invalid("anchors", self.anchors[-1].tenths, "the last anchor is the top of dial")
        previous = self.anchors[0]
        for anchor in self.anchors[1:]:
            if anchor.tenths <= previous.tenths:
                raise Invalid("anchors", anchor.tenths, "the table climbs the dial in order")
            if anchor.unit_points <= previous.unit_points:
                raise Invalid("anchors", anchor.unit_points, "the table never doubles back")
            previous = anchor

    def parse(self, text: str) -> int:
        """Read a score off a page and return it in tenths.

        Channels print ``8``, ``8.4`` and ``8,4`` depending on the locale they
        served the page in. All three are the same score.
        """
        cleaned = text.strip().replace(",", ".")
        if not cleaned:
            raise Invalid("score", text, "the page carried no score")
        whole, _, fraction = cleaned.partition(".")
        if len(fraction) > 1:
            raise Invalid("score", text, "channels publish at most one decimal place")
        try:
            tenths = int(whole) * 10 + (int(fraction) if fraction else 0)
        except ValueError:
            raise Invalid("score", text, "a score is a number") from None
        if not self.low_tenths <= tenths <= self.high_tenths:
            raise Invalid("score", text, f"this dial runs from {self.low_tenths} to a hundred")
        return tenths

    def normalise(self, tenths: int) -> int:
        """Return the unit points for a score, interpolating between anchors."""
        if not self.low_tenths <= tenths <= self.high_tenths:
            raise Invalid("tenths", tenths, "the score is off the end of this dial")
        lower = self.anchors[0]
        for anchor in self.anchors:
            if anchor.tenths == tenths:
                return anchor.unit_points
            if anchor.tenths > tenths:
                span = anchor.tenths - lower.tenths
                rise = anchor.unit_points - lower.unit_points
                offset = tenths - lower.tenths
                return lower.unit_points + (offset * rise + span // 2) // span
            lower = anchor
        return self.anchors[-1].unit_points

    def label_for(self, tenths: int) -> str:
        """Return the channel's own word for a score, taking the anchor at or below."""
        if not self.low_tenths <= tenths <= self.high_tenths:
            raise Invalid("tenths", tenths, "the score is off the end of this dial")
        word = self.anchors[0].label
        for anchor in self.anchors:
            if anchor.tenths > tenths:
                break
            word = anchor.label
        return word


FIVE_STAR = ScoreScale(
    "five-star",
    10,
    50,
    (
        Anchor(10, 4, "terrible"),
        Anchor(20, 22, "poor"),
        Anchor(30, 48, "average"),
        Anchor(40, 76, "very good"),
        Anchor(50, 96, "excellent"),
    ),
)
"""The five star dial. The agreed table is steep at the top because a guest who
gives four stars out of five on this channel is not saying eighty percent."""

TEN_POINT = ScoreScale(
    "ten-point",
    10,
    100,
    (
        Anchor(10, 2, "very poor"),
        Anchor(50, 30, "poor"),
        Anchor(70, 58, "good"),
        Anchor(80, 74, "very good"),
        Anchor(90, 86, "superb"),
        Anchor(100, 98, "exceptional"),
    ),
)
"""The ten point dial. Nothing below five is ever printed on it in practice,
which is why the foot of the table is a single long segment."""

SCALES: dict[str, ScoreScale] = {scale.slug: scale for scale in (FIVE_STAR, TEN_POINT)}


def scale_for(slug: str) -> ScoreScale:
    """Return a published scale by name, or refuse the name."""
    try:
        return SCALES[slug]
    except KeyError:
        raise Invalid("scale", slug, "no such published scale") from None
