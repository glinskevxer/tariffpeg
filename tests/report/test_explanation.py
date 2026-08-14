"""A number an operator can argue with, rather than one they can only accept."""

from __future__ import annotations

from tariffpeg.claims.pack import PACK
from tariffpeg.model.channel import Channel
from tariffpeg.model.licence import Licence
from tariffpeg.model.outcome import Disposition
from tariffpeg.model.period import StayMonth
from tariffpeg.report.casefile import CaseFile, build
from tariffpeg.report.explanation import explain, heaviest
from tests.report.test_casefile import QUIET, captures, coverage, notice, reviews
from tests.triage.conftest import a_review

AT = StayMonth(2025, 9)


def file_for(anchor: Licence, channels: dict[str, Channel]) -> CaseFile:
    return build(anchor, reviews(), channels, coverage(), [], PACK, AT, captures())


def test_the_explanation_names_the_licence_and_the_month(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    lines = explain(file_for(anchor, channels)).lines()
    assert lines[0].startswith(anchor.ref)
    assert lines[1] == "decided at 2025-09"


def test_every_contradiction_is_listed_with_its_rule_and_its_age(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    found = explain(file_for(anchor, channels)).evidence()
    assert any("rule lift-absent" in line for line in found)
    assert any("months old" in line for line in found)
    assert any("strength" in line for line in found)


def test_the_multiplication_by_the_voices_is_shown(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    found = explain(file_for(anchor, channels)).corroboration()
    assert any("raw times" in line for line in found)
    assert any("independent channels" in line for line in found)


def test_the_addition_shows_the_heaviest_finding_first(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    found = explain(file_for(anchor, channels)).arithmetic()
    assert found[0].startswith("the heaviest finding is lift")
    assert any("the evidence scores" in line for line in found)


def test_an_access_finding_is_called_out_on_its_own(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    found = explain(file_for(anchor, channels)).arithmetic()
    assert any("access findings" in line for line in found)


def test_a_licence_with_nothing_against_it_says_the_score_is_nothing(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    quiet = build(anchor, (a_review("1", QUIET),), channels, coverage(), [], PACK, AT, captures())
    found = explain(quiet)
    assert found.arithmetic() == ("nothing was found, so the score is nought",)
    assert any("nothing here is heavy enough" in line for line in found.outcome())


def test_a_file_with_no_notice_says_nothing_was_discounted(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    found = explain(file_for(anchor, channels)).discounts()
    assert found == ("no accepted notice has discounted anything",)


def test_an_accepted_notice_shows_what_it_cut(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    with_notice = build(anchor, reviews(), channels, coverage(), [notice()], PACK, AT, captures())
    found = explain(with_notice).discounts()
    assert any("cut from" in line for line in found)


def test_a_short_sample_says_it_has_to_be_completed(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    held = build(anchor, reviews(), channels, coverage(satisfied=False), [], PACK, AT, captures())
    found = explain(held).outcome()
    assert any("has to be completed" in line for line in found)


def test_the_whole_explanation_reads_as_headed_blocks(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    lines = explain(file_for(anchor, channels)).lines()
    for heading in (
        "WHAT WAS FOUND",
        "WHAT A NOTICE DISCOUNTED",
        "WHAT THE VOICES MULTIPLIED IT BY",
        "HOW IT WAS ADDED UP",
        "WHAT CAME OF IT",
    ):
        assert heading in lines
    assert lines[-1] != ""


def test_the_finding_that_decided_it_can_be_asked_for(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    leading = heaviest(file_for(anchor, channels))
    assert leading is not None
    assert leading.claim_key == "lift"


def test_a_file_with_nothing_in_it_has_no_deciding_finding(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    quiet = build(anchor, (a_review("1", QUIET),), channels, coverage(), [], PACK, AT, captures())
    assert heaviest(quiet) is None
    assert quiet.decision.disposition is Disposition.NO_ACTION


def test_an_explanation_is_the_shape_it_says_it_is(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    from tariffpeg.report.explanation import Explanation

    found = explain(file_for(anchor, channels))
    assert isinstance(found, Explanation)
    assert found.file.licence.serial == anchor.serial


def test_the_explanation_says_how_a_finding_sits_across_the_rooms(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    found = explain(file_for(anchor, channels)).rooms()
    assert any("no channel published a room class" in line for line in found)


def test_the_rooms_block_has_a_heading_of_its_own(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    assert "HOW IT SITS ACROSS THE ROOMS" in explain(file_for(anchor, channels)).lines()


def test_a_second_finding_is_added_at_the_tail_share(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    two = (
        a_review("1", "There is no lift at all and we carried the cases up."),
        a_review("2", "They have no lift, which the listing never mentioned."),
        a_review(
            "3",
            "Breakfast was charged at twelve pounds a head, which the listing"
            " did not mention anywhere before we booked the room.",
            channel="atlas",
        ),
        a_review(
            "4",
            "Breakfast was charged at ten pounds a head and we had expected"
            " it to come with the rate as the listing said.",
        ),
    )
    wider = anchor.with_particular("breakfast_included", True)
    file = build(wider, two, channels, coverage(), [], PACK, AT, captures())
    lines = explain(file).arithmetic()
    assert any("adds" in line and "which is" in line for line in lines)
