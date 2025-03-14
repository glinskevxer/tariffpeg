"""Normalisation follows the agreed table, and the table is not a straight line."""

from __future__ import annotations

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.model.scale import (
    FIVE_STAR,
    SCALES,
    TEN_POINT,
    Anchor,
    ScoreScale,
    scale_for,
)


def test_an_anchor_stays_inside_the_unit_scale() -> None:
    with pytest.raises(Invalid, match="nought to a hundred"):
        Anchor(10, 101, "impossible")
    with pytest.raises(Invalid, match="nought to a hundred"):
        Anchor(10, -1, "impossible")


def test_an_anchor_carries_the_channels_own_word() -> None:
    with pytest.raises(Invalid, match="channel's own word"):
        Anchor(10, 4, "  ")


def test_a_table_has_to_reach_both_ends_of_the_dial() -> None:
    with pytest.raises(Invalid, match="foot of dial"):
        ScoreScale("x", 10, 50, (Anchor(20, 5, "a"), Anchor(50, 90, "b")))
    with pytest.raises(Invalid, match="top of dial"):
        ScoreScale("x", 10, 50, (Anchor(10, 5, "a"), Anchor(40, 90, "b")))


def test_a_table_needs_at_least_both_ends() -> None:
    with pytest.raises(Invalid, match="both ends"):
        ScoreScale("x", 10, 50, (Anchor(10, 5, "a"),))


def test_a_table_climbs_in_order_and_never_doubles_back() -> None:
    with pytest.raises(Invalid, match="climbs the dial in order"):
        ScoreScale("x", 10, 50, (Anchor(10, 5, "a"), Anchor(10, 40, "b"), Anchor(50, 90, "c")))
    with pytest.raises(Invalid, match="never doubles back"):
        ScoreScale("x", 10, 50, (Anchor(10, 50, "a"), Anchor(30, 40, "b"), Anchor(50, 90, "c")))


def test_a_dial_whose_top_is_under_its_foot_is_refused() -> None:
    with pytest.raises(Invalid, match="above its foot"):
        ScoreScale("x", 50, 10, (Anchor(50, 5, "a"), Anchor(10, 90, "b")))


def test_a_scale_is_named_with_a_slug() -> None:
    with pytest.raises(Invalid, match="named with a slug"):
        ScoreScale("Five Star", 10, 50, (Anchor(10, 5, "a"), Anchor(50, 90, "b")))


def test_a_whole_number_and_a_decimal_both_read_as_tenths() -> None:
    assert TEN_POINT.parse("8") == 80
    assert TEN_POINT.parse("8.4") == 84
    assert TEN_POINT.parse(" 10 ") == 100


def test_a_comma_decimal_reads_the_same_as_a_full_stop() -> None:
    assert TEN_POINT.parse("8,4") == 84


def test_more_than_one_decimal_place_is_refused() -> None:
    with pytest.raises(Invalid, match="one decimal place"):
        TEN_POINT.parse("8.45")


def test_a_blank_or_non_numeric_score_is_refused() -> None:
    with pytest.raises(Invalid, match="no score"):
        TEN_POINT.parse("   ")
    with pytest.raises(Invalid, match="is a number"):
        TEN_POINT.parse("great")


def test_a_score_off_the_end_of_the_dial_is_refused() -> None:
    with pytest.raises(Invalid, match="this dial runs"):
        TEN_POINT.parse("11")
    with pytest.raises(Invalid, match="this dial runs"):
        FIVE_STAR.parse("0")


def test_an_anchor_normalises_to_exactly_its_agreed_value() -> None:
    for anchor in TEN_POINT.anchors:
        assert TEN_POINT.normalise(anchor.tenths) == anchor.unit_points
    for anchor in FIVE_STAR.anchors:
        assert FIVE_STAR.normalise(anchor.tenths) == anchor.unit_points


def test_a_score_between_anchors_lands_between_their_unit_points() -> None:
    assert 74 < TEN_POINT.normalise(85) < 86
    assert 58 < TEN_POINT.normalise(75) < 74


def test_normalisation_is_not_a_plain_rescale_of_the_dial() -> None:
    # Eight out of ten is eighty percent of the dial and nowhere near eighty points.
    assert TEN_POINT.normalise(80) == 74
    # Four stars out of five is eighty percent of that dial and lands somewhere else again.
    assert FIVE_STAR.normalise(40) == 76


def test_normalisation_never_goes_down_as_the_score_goes_up() -> None:
    for scale in (FIVE_STAR, TEN_POINT):
        seen = [scale.normalise(t) for t in range(scale.low_tenths, scale.high_tenths + 1)]
        assert seen == sorted(seen)


def test_a_score_off_the_dial_cannot_be_normalised() -> None:
    with pytest.raises(Invalid, match="off the end"):
        TEN_POINT.normalise(5)
    with pytest.raises(Invalid, match="off the end"):
        TEN_POINT.normalise(110)


def test_the_label_is_the_anchor_at_or_below_the_score() -> None:
    assert TEN_POINT.label_for(80) == "very good"
    assert TEN_POINT.label_for(85) == "very good"
    assert TEN_POINT.label_for(90) == "superb"
    assert TEN_POINT.label_for(10) == "very poor"
    assert TEN_POINT.label_for(100) == "exceptional"


def test_a_label_cannot_be_asked_for_off_the_dial() -> None:
    with pytest.raises(Invalid, match="off the end"):
        FIVE_STAR.label_for(60)


def test_the_published_scales_are_reachable_by_name() -> None:
    assert scale_for("ten-point") is TEN_POINT
    assert scale_for("five-star") is FIVE_STAR
    assert set(SCALES) == {"ten-point", "five-star"}
    with pytest.raises(Invalid, match="no such published scale"):
        scale_for("thumbs")
