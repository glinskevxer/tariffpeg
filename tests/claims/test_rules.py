"""A lift that is out of order needs company before it is worth an inspection."""

from __future__ import annotations

import pytest

from tariffpeg.claims.rules import (
    Assertion,
    ClaimRule,
    Persistence,
    Polarity,
    RulePack,
)
from tariffpeg.errors import Invalid

NO_LIFT = ClaimRule(
    "lift-absent",
    "lift",
    "(there is no|there was no|they have no) ... lift",
    Polarity.DENIES,
    Persistence.STRUCTURAL,
    5,
)
LIFT_BROKEN = ClaimRule(
    "lift-out-of-order",
    "lift",
    "lift ... (out of order|not working|broken)",
    Polarity.DENIES,
    Persistence.TRANSIENT,
    2,
)
LIFT_USED = ClaimRule(
    "lift-used",
    "lift",
    "(took the lift|used the lift|lift to our floor)",
    Polarity.AFFIRMS,
    Persistence.STRUCTURAL,
    3,
)
ROOMS_COUNTED = ClaimRule(
    "rooms-counted",
    "let_rooms",
    "only # rooms",
    Polarity.STATES,
    Persistence.STRUCTURAL,
    2,
)


def test_a_rule_needs_an_id_to_be_cited_by() -> None:
    with pytest.raises(Invalid, match="id to be cited by"):
        ClaimRule("  ", "lift", "no lift", Polarity.DENIES, Persistence.STRUCTURAL, 3)


def test_a_rule_about_a_particular_nobody_registers_is_refused() -> None:
    with pytest.raises(Invalid, match="no such particular"):
        ClaimRule("x", "sauna", "no sauna", Polarity.DENIES, Persistence.STRUCTURAL, 3)


def test_a_rule_that_weighs_nothing_or_too_much_is_refused() -> None:
    for weight in (0, 6):
        with pytest.raises(Invalid, match="weighs one to"):
            ClaimRule("x", "lift", "no lift", Polarity.DENIES, Persistence.STRUCTURAL, weight)


def test_a_rule_with_a_broken_pattern_is_refused_when_it_is_written() -> None:
    with pytest.raises(Invalid, match="at least two options"):
        ClaimRule("x", "lift", "(lift)", Polarity.DENIES, Persistence.STRUCTURAL, 3)


def test_a_yes_or_no_particular_cannot_have_a_value_stated_about_it() -> None:
    with pytest.raises(Invalid, match="has no value"):
        ClaimRule("x", "lift", "only # lifts", Polarity.STATES, Persistence.STRUCTURAL, 3)


def test_a_measured_particular_is_contradicted_by_a_value_and_not_by_a_direction() -> None:
    with pytest.raises(Invalid, match="contradicted by a value"):
        ClaimRule("x", "let_rooms", "no rooms", Polarity.DENIES, Persistence.STRUCTURAL, 3)


def test_a_rule_that_states_a_value_has_to_capture_one() -> None:
    with pytest.raises(Invalid, match="states a value captures one"):
        ClaimRule("x", "let_rooms", "only a few rooms", Polarity.STATES, Persistence.STRUCTURAL, 3)


def test_a_rule_that_does_not_state_a_value_must_not_capture_one() -> None:
    with pytest.raises(Invalid, match="only a rule that states"):
        ClaimRule("x", "lift", "no # lift", Polarity.DENIES, Persistence.STRUCTURAL, 3)


def test_a_pack_reads_the_assertions_a_body_carries() -> None:
    pack = RulePack(1, (NO_LIFT, LIFT_BROKEN, LIFT_USED))
    found = pack.read("There is no lift and we were on the third floor.")
    assert [assertion.rule_id for assertion in found] == ["lift-absent"]
    assert found[0].polarity is Polarity.DENIES
    assert found[0].structural


def test_the_quote_is_the_words_the_rule_matched() -> None:
    pack = RulePack(1, (LIFT_BROKEN,))
    found = pack.read("The lift was out of order for the whole week.")
    assert found[0].quote == "lift was out of order"


def test_a_transient_assertion_is_marked_as_one() -> None:
    pack = RulePack(1, (LIFT_BROKEN,))
    found = pack.read("The lift was out of order.")
    assert not found[0].structural
    assert found[0].persistence is Persistence.TRANSIENT


def test_a_rule_that_states_a_value_carries_the_number_it_found() -> None:
    pack = RulePack(1, (ROOMS_COUNTED,))
    found = pack.read("They let only 4 rooms in the whole house.")
    assert found[0].value == 4
    assert found[0].polarity is Polarity.STATES


def test_a_rule_matching_twice_still_asserts_once() -> None:
    pack = RulePack(1, (LIFT_USED,))
    found = pack.read("We took the lift up and we took the lift down.")
    assert len(found) == 1


def test_several_rules_can_speak_to_one_particular_at_once() -> None:
    pack = RulePack(1, (NO_LIFT, LIFT_BROKEN))
    found = pack.read("There is no lift, and the lift they do have is broken.")
    assert {assertion.rule_id for assertion in found} == {"lift-absent", "lift-out-of-order"}


def test_a_body_with_nothing_to_say_yields_nothing() -> None:
    pack = RulePack(1, (NO_LIFT, LIFT_BROKEN, LIFT_USED))
    assert pack.read("Breakfast was lovely and the beds were comfortable.") == ()


def test_a_pack_lists_its_rules_by_particular() -> None:
    pack = RulePack(1, (NO_LIFT, LIFT_BROKEN, ROOMS_COUNTED))
    assert len(pack.for_claim("lift")) == 2
    assert len(pack.for_claim("let_rooms")) == 1
    assert pack.for_claim("pets_accepted") == ()
    assert pack.claim_keys() == ("let_rooms", "lift")


def test_a_rule_can_be_looked_up_by_the_id_a_bundle_cites() -> None:
    pack = RulePack(1, (NO_LIFT, LIFT_BROKEN))
    assert pack.rule("lift-absent") is NO_LIFT
    with pytest.raises(Invalid, match="no such rule"):
        pack.rule("nothing-like-this")


def test_a_pack_with_a_repeated_rule_id_is_refused() -> None:
    twin = ClaimRule("lift-absent", "lift", "no lift", Polarity.DENIES, Persistence.STRUCTURAL, 3)
    with pytest.raises(Invalid, match="appears once in a pack"):
        RulePack(1, (NO_LIFT, twin))


def test_an_empty_pack_or_a_version_below_one_is_refused() -> None:
    with pytest.raises(Invalid, match="reads nothing"):
        RulePack(1, ())
    with pytest.raises(Invalid, match="start at one"):
        RulePack(0, (NO_LIFT,))


def test_an_assertion_with_no_value_carries_none() -> None:
    assertion = Assertion("x", "lift", Polarity.DENIES, Persistence.STRUCTURAL, 3, "no lift")
    assert assertion.value is None
    assert assertion.structural
