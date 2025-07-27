"""Four copies of one guest is one voice, and one voice is not a reason to send anybody."""

from __future__ import annotations

from tariffpeg.model.channel import Channel
from tariffpeg.model.licence import Licence
from tariffpeg.model.period import StayMonth
from tariffpeg.model.review import Review
from tariffpeg.triage.corroborate import (
    MANY_VOICES,
    SPREAD_BONUS,
    Finding,
    build,
    corroboration_for,
)
from tariffpeg.triage.weight import weigh_all
from tests.triage.conftest import (
    BREAKFAST,
    BROKEN_LIFT,
    NO_LIFT,
    NO_LIFT_AGAIN,
    a_review,
    a_weighed,
    contradictions,
)

AT = StayMonth(2025, 9)


def findings_for(
    reviews: tuple[Review, ...], licence: Licence, channels: dict[str, Channel]
) -> tuple[Finding, ...]:
    weighed = weigh_all(contradictions(reviews, licence), AT)
    return build(weighed, {review.key: review for review in reviews}, channels, licence)


def test_one_voice_is_worth_less_than_it_says_on_its_face(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    found = findings_for((a_review("1", NO_LIFT),), anchor, channels)
    assert len(found) == 1
    assert found[0].voices == 1
    assert found[0].corroboration < 1.0
    assert found[0].score < found[0].raw_weight


def test_two_voices_on_two_channels_are_worth_more_than_two_on_one(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    one_channel = (a_review("1", NO_LIFT), a_review("2", NO_LIFT_AGAIN))
    two_channels = (a_review("1", NO_LIFT), a_review("2", NO_LIFT_AGAIN, "quayside"))
    narrow = findings_for(one_channel, anchor, channels)[0]
    wide = findings_for(two_channels, anchor, channels)[0]
    assert wide.corroboration > narrow.corroboration
    assert wide.score > narrow.score


def test_a_syndicated_copy_does_not_add_a_voice(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    reviews = (a_review("1", NO_LIFT), a_review("77", NO_LIFT, "atlas"))
    found = findings_for(reviews, anchor, channels)[0]
    assert found.voices == 1
    assert found.channels == ("seaboard",)


def test_more_voices_raise_the_multiplier_up_to_a_ceiling() -> None:
    assert corroboration_for(0, 0) == 0.0
    assert corroboration_for(1, 1) < corroboration_for(2, 1)
    assert corroboration_for(2, 1) < corroboration_for(3, 1)
    assert corroboration_for(4, 1) == MANY_VOICES
    assert corroboration_for(40, 1) == MANY_VOICES


def test_the_spread_bonus_applies_only_when_there_are_voices() -> None:
    assert corroboration_for(0, 3) == 0.0
    assert corroboration_for(2, 2) == round(1.0 * SPREAD_BONUS, 4)


def test_one_finding_comes_back_per_particular(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    reviews = (a_review("1", NO_LIFT), a_review("2", BREAKFAST))
    breakfast_licence = anchor.with_particular("breakfast_included", True)
    found = findings_for(reviews, breakfast_licence, channels)
    assert {finding.claim_key for finding in found} == {"lift", "breakfast_included"}


def test_the_findings_come_back_heaviest_first(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    reviews = (
        a_review("1", NO_LIFT),
        a_review("2", NO_LIFT_AGAIN, "quayside"),
        a_review("3", BREAKFAST),
    )
    breakfast_licence = anchor.with_particular("breakfast_included", True)
    found = findings_for(reviews, breakfast_licence, channels)
    assert found[0].claim_key == "lift"
    assert found[0].score > found[1].score


def test_a_finding_carries_what_the_licence_declared(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    found = findings_for((a_review("1", NO_LIFT),), anchor, channels)[0]
    assert found.declared == "yes"
    assert found.licence_serial == 4021


def test_a_finding_counts_how_many_of_its_contradictions_are_structural(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    reviews = (a_review("1", NO_LIFT), a_review("2", BROKEN_LIFT, "quayside"))
    found = findings_for(reviews, anchor, channels)[0]
    # The first review sets off two rules, the missing lift and the flights of stairs.
    assert len(found.weighed) == 3
    assert found.structural_voices == 2


def test_the_case_file_leads_with_the_heaviest_contradiction(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    reviews = (a_review("1", BROKEN_LIFT), a_review("2", NO_LIFT, "quayside"))
    found = findings_for(reviews, anchor, channels)[0]
    leading = found.heaviest()
    assert leading is not None
    assert leading.review_key == "quayside:2"


def test_a_finding_with_nothing_in_it_leads_with_nothing() -> None:
    empty = Finding(4021, "lift", "yes", (), 0, ())
    assert empty.heaviest() is None
    assert empty.raw_weight == 0.0
    assert empty.score == 0.0


def test_the_line_names_the_particular_the_score_and_the_channels(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    found = findings_for((a_review("1", NO_LIFT),), anchor, channels)[0]
    line = found.line()
    assert line.startswith("lift (a passenger lift serves the guest floors):")
    assert "from 1 voices on seaboard" in line


def test_a_finding_with_no_independent_channel_says_so() -> None:
    empty = Finding(4021, "lift", "yes", (a_weighed(),), 1, ())
    assert "no independent channel" in empty.line()


def test_a_contradiction_whose_review_is_gone_still_weighs(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    found = build((a_weighed(),), {}, channels, anchor)
    assert found[0].voices == 0
    assert found[0].raw_weight == 5.0
    assert found[0].score == 0.0


def test_building_from_nothing_gives_nothing(anchor: Licence, channels: dict[str, Channel]) -> None:
    assert build((), {}, channels, anchor) == ()
