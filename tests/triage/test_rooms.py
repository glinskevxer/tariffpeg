"""Six guests in the attic twin is a plumbing run, six spread out is the boiler."""

from __future__ import annotations

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.model.period import StayMonth
from tariffpeg.model.review import Review
from tariffpeg.triage.corroborate import Finding
from tariffpeg.triage.rooms import (
    CONCENTRATION,
    LEAST_VOICES,
    UNKNOWN,
    concentrated_only,
    share_in,
    spread,
    spreads,
)
from tariffpeg.triage.weight import Weighed
from tests.triage.conftest import a_weighed

DIGEST = "sha256:" + "a" * 64
BODY = "The shower ran cold every morning of the week we were there in the attic."


def review(number: str, room_class: str) -> Review:
    return Review(
        channel="seaboard",
        channel_review_id=number,
        licence_serial=4021,
        stay=StayMonth(2025, 7),
        unit_points=74,
        raw_score="8.4",
        body=f"{BODY} Filed as {number}.",
        capture_digest=DIGEST,
        profile_key="seaboard/v1",
        room_class=room_class,
    )


def finding_of(*classes: str) -> tuple[Finding, dict[str, Review]]:
    weighed: list[Weighed] = []
    reviews: dict[str, Review] = {}
    for number, room_class in enumerate(classes):
        key = f"seaboard:{number}"
        weighed.append(a_weighed(claim_key="lift", review_key=key))
        reviews[key] = review(str(number), room_class)
    return Finding(4021, "lift", "yes", tuple(weighed), len(classes), ("seaboard",)), reviews


def test_voices_all_in_one_class_read_as_concentrated() -> None:
    finding, reviews = finding_of("attic-twin", "attic-twin", "attic-twin")
    found = spread(finding, reviews)
    assert found.concentrated
    assert found.dominant == "attic-twin"
    assert "100% of the voices" in found.line()


def test_voices_spread_across_classes_do_not_read_as_concentrated() -> None:
    finding, reviews = finding_of("attic-twin", "sea-view", "ground-double")
    found = spread(finding, reviews)
    assert not found.concentrated
    assert "spread across the classes" in found.line()
    assert "attic-twin 1" in found.line()


def test_one_stray_voice_does_not_break_a_concentration() -> None:
    finding, reviews = finding_of(*(["attic-twin"] * 9), "sea-view")
    found = spread(finding, reviews)
    assert found.concentrated
    assert share_in(found, "attic-twin") >= CONCENTRATION


def test_too_few_voices_say_nothing_about_the_shape() -> None:
    finding, reviews = finding_of("attic-twin", "attic-twin")
    found = spread(finding, reviews)
    assert not found.concentrated
    assert "too few voices" in found.line()
    assert LEAST_VOICES == 3


def test_a_finding_where_no_channel_published_a_class_says_so() -> None:
    finding, reviews = finding_of("", "", "")
    found = spread(finding, reviews)
    assert found.known == 0
    assert found.dominant == ""
    assert not found.concentrated
    assert "no channel published a room class" in found.line()


def test_the_voices_with_no_class_are_counted_apart() -> None:
    finding, reviews = finding_of("attic-twin", "attic-twin", "attic-twin", "")
    found = spread(finding, reviews)
    assert found.counted[UNKNOWN] == 1
    assert found.known == 3
    assert found.concentrated


def test_a_contradiction_whose_review_is_gone_is_not_counted() -> None:
    finding, reviews = finding_of("attic-twin", "attic-twin")
    del reviews["seaboard:1"]
    found = spread(finding, reviews)
    assert found.voices == 1


def test_the_dominant_class_is_stable_when_two_tie() -> None:
    finding, reviews = finding_of("attic-twin", "sea-view")
    assert spread(finding, reviews).dominant == "attic-twin"


def test_every_finding_gets_a_shape_in_the_order_it_was_given() -> None:
    one, reviews = finding_of("attic-twin", "attic-twin", "attic-twin")
    two = Finding(4021, "breakfast_included", "yes", one.weighed, 3, ("seaboard",))
    found = spreads([one, two], reviews)
    assert [item.claim_key for item in found] == ["lift", "breakfast_included"]


def test_only_the_concentrated_findings_can_be_asked_for() -> None:
    one, reviews = finding_of("attic-twin", "attic-twin", "attic-twin")
    two, more = finding_of("attic-twin", "sea-view", "ground-double")
    found = concentrated_only(spreads([one], reviews) + spreads([two], more))
    assert len(found) == 1


def test_the_share_in_a_class_nobody_named_is_nothing() -> None:
    finding, reviews = finding_of("attic-twin", "attic-twin", "attic-twin")
    assert share_in(spread(finding, reviews), "sea-view") == 0.0


def test_asking_about_a_class_with_no_name_is_refused() -> None:
    finding, reviews = finding_of("attic-twin")
    with pytest.raises(Invalid, match="a room class has a name"):
        share_in(spread(finding, reviews), "   ")


def test_a_shape_with_nothing_in_it_says_nothing() -> None:
    from tariffpeg.triage.rooms import Spread

    empty = Spread("lift", {}, 0)
    assert isinstance(empty, Spread)
    assert empty.known == 0
    assert not empty.concentrated
