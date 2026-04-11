"""Nobody has ever been called in over a beach that turned out to be nearer."""

from __future__ import annotations

import datetime as dt

from tariffpeg.claims.contradiction import by_claim, contradicts, read_all, read_review
from tariffpeg.claims.pack import PACK
from tariffpeg.claims.rules import Assertion, Persistence, Polarity
from tariffpeg.model.licence import Licence
from tariffpeg.model.period import StayMonth
from tariffpeg.model.review import Review

DIGEST = "sha256:" + "a" * 64


def licence(**particulars: object) -> Licence:
    declared: dict[str, object] = {
        "grading_band": 3,
        "let_rooms": 9,
        "bed_spaces": 18,
        "lift": True,
        "breakfast_included": True,
        "shore_distance": 220,
    }
    declared.update(particulars)
    return Licence(
        serial=4021,
        trading_name="The Anchor Rooms",
        operator_name="Pellow and Daughter",
        locality="Porthgwarra",
        period_start=dt.date(2025, 4, 1),
        period_end=dt.date(2026, 3, 31),
        particulars=declared,  # type: ignore[arg-type]
    )


def review(body: str, number: str = "1", month: int = 7) -> Review:
    return Review(
        channel="seaboard",
        channel_review_id=number,
        licence_serial=4021,
        stay=StayMonth(2025, month),
        unit_points=74,
        raw_score="8.4",
        body=body,
        capture_digest=DIGEST,
        profile_key="seaboard/v1",
    )


def test_a_guest_denying_a_flag_the_licence_claims_is_a_contradiction() -> None:
    found = read_review(
        review("There is no lift and our room was on the third floor."), licence(), PACK
    )
    assert len(found) == 1
    assert found[0].claim_key == "lift"
    assert found[0].declared == "yes"
    assert found[0].asserted == "no"


def test_a_guest_affirming_a_flag_the_licence_denies_is_a_contradiction() -> None:
    found = read_review(
        review("We took the lift up with the cases, which helped a lot."),
        licence(lift=False),
        PACK,
    )
    assert len(found) == 1
    assert found[0].asserted == "yes"
    assert found[0].declared == "no"


def test_a_guest_agreeing_with_the_licence_raises_nothing() -> None:
    body = "We took the lift up with the cases, which helped us a great deal."
    assert read_review(review(body), licence(), PACK) == ()


def test_a_particular_the_licence_never_declared_cannot_be_contradicted() -> None:
    body = "They would not take our dog despite what the listing said about it."
    assert read_review(review(body), licence(), PACK) == ()


def test_a_review_too_short_to_say_anything_raises_nothing() -> None:
    assert read_review(review("No lift."), licence(), PACK) == ()


def test_a_count_outside_the_tolerance_is_a_contradiction() -> None:
    found = read_review(
        review("There are only 4 rooms in the whole place, which was not what we booked."),
        licence(),
        PACK,
    )
    assert len(found) == 1
    assert found[0].claim_key == "let_rooms"
    assert found[0].declared == "9"
    assert found[0].asserted == "4"


def test_a_count_inside_the_tolerance_is_not_a_contradiction() -> None:
    body = "It sleeps 17 at a push, which was plenty for the eight of us."
    assert read_review(review(body), licence(), PACK) == ()


def test_a_count_outside_the_tolerance_in_either_direction_counts() -> None:
    body = "It sleeps 30 at a push, which was plenty for our party of eight."
    found = read_review(review(body), licence(), PACK)
    assert [item.claim_key for item in found] == ["bed_spaces"]


def test_a_distance_further_than_the_licence_says_is_a_contradiction() -> None:
    found = read_review(
        review("It is a good 900 metres to the beach, and all of it uphill."), licence(), PACK
    )
    assert len(found) == 1
    assert found[0].claim_key == "shore_distance"
    assert found[0].declared == "220 m"
    assert found[0].asserted == "900 m"


def test_a_distance_nearer_than_the_licence_says_is_not_a_contradiction() -> None:
    body = "It is only 50 metres to the beach, you can hear the sea from bed."
    assert read_review(review(body), licence(), PACK) == ()


def test_a_distance_inside_the_tolerance_is_not_a_contradiction() -> None:
    body = "It is about 300 metres to the beach, which was fine with the buggy."
    assert read_review(review(body), licence(), PACK) == ()


def test_a_walk_in_minutes_is_converted_before_it_is_compared() -> None:
    body = "About 15 minutes to the shore on foot, which we did not mind at all."
    found = read_review(review(body), licence(), PACK)
    assert found[0].claim_key == "shore_distance"
    assert found[0].asserted == "1200 m"


def test_a_transient_contradiction_is_marked_apart_from_a_structural_one() -> None:
    absent = read_review(
        review("There is no lift and our room was on the third floor here."), licence(), PACK
    )
    broken = read_review(
        review("The lift was out of order for the whole of the week we stayed."), licence(), PACK
    )
    assert absent[0].structural
    assert not broken[0].structural
    assert absent[0].strength > broken[0].strength


def test_the_line_a_case_file_prints_names_both_sides_and_the_month() -> None:
    found = read_review(
        review("There is no lift and our room was on the third floor here."), licence(), PACK
    )
    line = found[0].line()
    assert "the licence says yes" in line
    assert "a guest in 2025-07 said no" in line
    assert "passenger lift" in line


def test_a_stated_value_against_a_flag_contradicts_nothing() -> None:
    stated = Assertion("x", "lift", Polarity.STATES, Persistence.STRUCTURAL, 3, "q", 4)
    assert not contradicts(licence(), stated)


def test_an_assertion_with_no_value_against_a_count_contradicts_nothing() -> None:
    stated = Assertion("x", "let_rooms", Polarity.STATES, Persistence.STRUCTURAL, 3, "q", None)
    assert not contradicts(licence(), stated)


def test_reading_a_set_of_reviews_keeps_them_in_key_order() -> None:
    reviews = (
        review("There is no lift and our room was on the third floor here.", "9"),
        review("Breakfast was charged at twelve pounds a head every morning of our stay.", "1"),
    )
    found = read_all(reviews, licence(), PACK)
    assert [item.review_key for item in found] == ["seaboard:1", "seaboard:9"]


def test_contradictions_can_be_grouped_by_the_particular_they_speak_to() -> None:
    reviews = (
        review("There is no lift and our room was on the third floor here.", "1"),
        review("It is stairs only here, and four flights of them at that.", "2"),
        review("Breakfast was charged at twelve pounds a head every morning of our stay.", "3"),
    )
    grouped = by_claim(read_all(reviews, licence(), PACK))
    assert sorted(grouped) == ["breakfast_included", "lift"]
    assert len(grouped["lift"]) == 2
    assert len(grouped["breakfast_included"]) == 1


def test_grouping_an_empty_set_gives_back_an_empty_mapping() -> None:
    assert by_claim(()) == {}


def test_every_contradiction_names_the_review_the_licence_and_the_rule() -> None:
    found = read_review(
        review("There is no lift and our room was on the third floor here."), licence(), PACK
    )
    assert found[0].review_key == "seaboard:1"
    assert found[0].licence_serial == 4021
    assert found[0].rule_id == "lift-absent"
    assert "no lift" in found[0].quote


def test_a_contradiction_carries_the_language_it_was_translated_from() -> None:
    from dataclasses import replace

    body = "There is no lift and our room was on the third floor here."
    translated = replace(review(body), translated_from="fr")
    found = read_review(translated, licence(), PACK)
    assert found[0].translated
    assert found[0].translated_from == "fr"
    assert "through a translation from fr" in found[0].line()


def test_a_contradiction_from_words_the_guest_wrote_says_nothing_about_translation() -> None:
    body = "There is no lift and our room was on the third floor here."
    found = read_review(review(body), licence(), PACK)
    assert not found[0].translated
    assert "translation" not in found[0].line()
