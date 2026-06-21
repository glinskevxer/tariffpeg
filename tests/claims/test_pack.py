"""Every rule has a case that shows what it catches and one that shows what it leaves."""

from __future__ import annotations

import pytest

from tariffpeg.claims.pack import (
    ADDED_IN_TWO,
    METRES_A_MILE,
    METRES_A_MINUTE_WALKING,
    PACK,
    PACK_ONE,
    PACK_ONE_RULES,
    PACK_TWO,
    PACKS,
    pack_numbered,
    published_versions,
)
from tariffpeg.claims.rules import ClaimRule, Persistence, Polarity
from tariffpeg.errors import Invalid, NotFound

CATCHES = {
    "lift-absent": "There is no lift and our room was on the third floor.",
    "lift-out-of-order": "The lift was out of order all week.",
    "lift-used": "We took the lift up with the cases, which helped.",
    "stairs-only": "It is stairs only, and four flights of them.",
    "entrance-has-steps": "There are three steps to get in at the front.",
    "entrance-step-free": "Level access at the entrance, which suited us.",
    "bathroom-shared": "There is a shared bathroom for three of the rooms.",
    "bathroom-shared-after": "The bathroom was shared with two other rooms.",
    "bathroom-down-the-hall": "The toilet was down the hall from our room.",
    "bathroom-en-suite": "We had our own bathroom which was spotless.",
    "breakfast-charged": "Breakfast was charged at twelve pounds a head.",
    "breakfast-not-served": "There was no breakfast on the Sunday.",
    "breakfast-included": "Breakfast was included in the rate, which was good value.",
    "parking-absent": "There is no parking at the property at all.",
    "parking-off-site": "You park in the street, which fills up by six.",
    "parking-on-site": "We parked outside the door with no trouble.",
    "wifi-patchy": "The wifi was only in the lounge and nowhere else.",
    "wifi-down": "The internet was down for two days of our stay.",
    "wifi-worked": "The wifi was fine everywhere we tried it.",
    "pets-refused": "They would not take our dog despite the listing.",
    "pets-welcomed": "We brought our dog and nobody minded at all.",
    "late-arrival-refused": "Nobody was there when we arrived at eleven.",
    "late-arrival-staffed": "The owner waited up for us, which was kind.",
    "rooms-counted": "There are only 4 rooms in the whole place.",
    "rooms-in-the-house": "There are 6 bedrooms in the house.",
    "beds-counted": "It sleeps 12 at a push.",
    "parking-spaces-counted": "There are only 2 parking spaces for the whole house.",
    "shore-metres": "It is 400 metres to the beach, downhill.",
    "shore-minutes": "About 15 minutes to the shore on foot.",
    "shore-metres-after": "The beach is a good 600 metres from the door.",
    "shore-minutes-after": "The beach is about 12 minutes on foot.",
    "station-metres": "It is 900 metres to the station.",
    "station-minutes": "A 20 minute walk to the station with cases.",
    "station-metres-after": "The station is 900 metres away.",
    "station-minutes-after": "The station is 20 minutes walk from the door.",
    "entrance-down-to-the-door": "There are steps down to the door from the pavement.",
    "lift-too-small": "The lift was tiny and only fits two people with a case.",
    "bathroom-one-between": "One bathroom between the four rooms on that floor.",
    "breakfast-paid-for": "We paid extra for breakfast on both mornings.",
    "parking-full": "The car park was full every evening after seven.",
    "pets-charged-for": "They charged five pounds a night for the dog.",
    "late-arrival-key-box": "We let ourselves in with the key safe by the door.",
    "shore-miles": "It is a good 2 miles to the beach along the lane.",
    "station-miles": "About 3 miles to the station, so you want a car.",
    "rooms-in-the-name": "A 7 bedroom guest house right on the front.",
    "beds-sleeps-up-to": "It sleeps up to 9 with the sofa bed made up.",
    "parking-spaces-there-are": "There are 3 spaces at the side of the house.",
}

LEAVES_ALONE = (
    "Breakfast was lovely and the beds were comfortable.",
    "We had a fine week and would come back.",
    "The room was clean and the towels were changed daily.",
)


def test_every_rule_in_the_pack_has_a_case_that_shows_what_it_catches() -> None:
    assert set(CATCHES) == {rule.rule_id for rule in PACK.rules}


@pytest.mark.parametrize("rule_id", sorted(CATCHES))
def test_each_rule_catches_the_body_it_was_written_for(rule_id: str) -> None:
    body = CATCHES[rule_id]
    found = {assertion.rule_id for assertion in PACK.read(body)}
    assert rule_id in found, f"{rule_id} missed {body!r}"


@pytest.mark.parametrize("body", LEAVES_ALONE)
def test_an_ordinary_review_sets_nothing_off(body: str) -> None:
    assert PACK.read(body) == ()


def test_the_pack_speaks_to_every_particular_it_is_meant_to() -> None:
    assert set(PACK.claim_keys()) == {
        "lift",
        "step_free_entrance",
        "en_suite_all",
        "breakfast_included",
        "parking_on_site",
        "wifi_all_rooms",
        "pets_accepted",
        "late_arrival",
        "let_rooms",
        "bed_spaces",
        "parking_spaces",
        "shore_distance",
        "station_distance",
    }


def test_a_walk_in_minutes_is_converted_to_the_metres_the_licence_is_written_in() -> None:
    found = [a for a in PACK.read(CATCHES["shore-minutes"]) if a.rule_id == "shore-minutes"]
    assert found[0].value == 15 * METRES_A_MINUTE_WALKING


def test_a_distance_already_in_metres_is_not_converted() -> None:
    found = [a for a in PACK.read(CATCHES["shore-metres"]) if a.rule_id == "shore-metres"]
    assert found[0].value == 400


def test_a_missing_lift_is_structural_and_a_broken_one_is_not() -> None:
    absent = PACK.rule("lift-absent")
    broken = PACK.rule("lift-out-of-order")
    assert absent.persistence is Persistence.STRUCTURAL
    assert broken.persistence is Persistence.TRANSIENT
    assert absent.strength > broken.strength


def test_every_rule_that_denies_a_particular_has_a_partner_that_affirms_it() -> None:
    denied = {rule.claim_key for rule in PACK.rules if rule.polarity is Polarity.DENIES}
    affirmed = {rule.claim_key for rule in PACK.rules if rule.polarity is Polarity.AFFIRMS}
    assert denied <= affirmed


def test_every_rule_that_states_a_value_carries_a_scale() -> None:
    for rule in PACK.rules:
        if rule.polarity is Polarity.STATES:
            assert rule.value_scale >= 1


def test_a_scale_that_divides_is_refused() -> None:
    with pytest.raises(Invalid, match="does not divide"):
        ClaimRule(
            "x",
            "shore_distance",
            "# minutes",
            Polarity.STATES,
            Persistence.STRUCTURAL,
            2,
            value_scale=0,
        )


def test_only_a_stated_value_can_be_scaled() -> None:
    with pytest.raises(Invalid, match="only a stated value is scaled"):
        ClaimRule(
            "x",
            "lift",
            "no lift",
            Polarity.DENIES,
            Persistence.STRUCTURAL,
            2,
            value_scale=80,
        )


def test_the_pack_carries_a_version_a_case_file_can_cite() -> None:
    assert PACK.version == 2
    assert PACK is PACK_TWO
    assert len(PACK.rules) == len(PACK_ONE_RULES) + len(ADDED_IN_TWO)


def test_the_notes_say_what_the_two_lift_rules_are_for() -> None:
    assert "none at all" in PACK.rule("lift-absent").note
    assert "was not working" in PACK.rule("lift-out-of-order").note


def test_the_pack_in_force_is_the_last_one_published() -> None:
    assert PACKS[-1] is PACK
    assert published_versions() == (1, 2)


def test_an_older_pack_can_still_be_asked_for_by_number() -> None:
    assert pack_numbered(1) is PACK_ONE
    assert pack_numbered(2) is PACK_TWO


def test_a_pack_version_this_build_does_not_carry_is_refused() -> None:
    with pytest.raises(NotFound, match="rule pack"):
        pack_numbered(9)


def test_pack_one_is_left_alone_by_everything_pack_two_added() -> None:
    added = {rule.rule_id for rule in ADDED_IN_TWO}
    assert added & {rule.rule_id for rule in PACK_ONE_RULES} == set()
    assert PACK_ONE.rules == PACK_ONE_RULES


def test_a_body_only_pack_two_reads_says_nothing_under_pack_one() -> None:
    body = CATCHES["bathroom-one-between"]
    assert PACK_ONE.read(body) == ()
    assert {a.rule_id for a in PACK_TWO.read(body)} == {"bathroom-one-between"}


def test_a_distance_in_miles_is_converted_to_metres() -> None:
    found = [a for a in PACK.read(CATCHES["shore-miles"]) if a.rule_id == "shore-miles"]
    assert found[0].value == 2 * METRES_A_MILE


def test_a_distance_in_miles_is_weighed_lighter_than_one_in_metres() -> None:
    assert PACK.rule("shore-miles").strength < PACK.rule("shore-metres").strength


def test_a_full_car_park_says_there_is_one_but_only_for_that_week() -> None:
    rule = PACK.rule("parking-full")
    assert rule.polarity is Polarity.AFFIRMS
    assert rule.persistence is Persistence.TRANSIENT


def test_a_key_safe_is_read_as_a_door_nobody_staffs() -> None:
    rule = PACK.rule("late-arrival-key-box")
    assert rule.claim_key == "late_arrival"
    assert rule.polarity is Polarity.DENIES
