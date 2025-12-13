"""A lift does not appear, so a report that there is none keeps its weight."""

from __future__ import annotations

import pytest

from tariffpeg.claims.contradiction import Contradiction
from tariffpeg.claims.rules import Persistence
from tariffpeg.errors import Invalid
from tariffpeg.model.period import StayMonth
from tariffpeg.triage.weight import FLOOR, decay, half_life, weigh, weigh_all

STAY = StayMonth(2025, 7)


def contradiction(
    persistence: Persistence = Persistence.STRUCTURAL,
    strength: int = 5,
    review_key: str = "seaboard:1",
    claim_key: str = "lift",
) -> Contradiction:
    return Contradiction(
        review_key=review_key,
        licence_serial=4021,
        claim_key=claim_key,
        rule_id="lift-absent",
        persistence=persistence,
        strength=strength,
        quote="there is no lift",
        stay=STAY,
        declared="yes",
        asserted="no",
    )


def test_a_contradiction_from_this_month_keeps_its_whole_strength() -> None:
    found = weigh(contradiction(), STAY)
    assert found.months_old == 0
    assert found.weight == 5.0


def test_a_stay_in_the_future_is_treated_as_no_age_at_all() -> None:
    found = weigh(contradiction(), STAY.minus(3))
    assert found.months_old == -3
    assert found.weight == 5.0


def test_a_structural_contradiction_halves_over_its_own_half_life() -> None:
    assert decay(24, Persistence.STRUCTURAL) == pytest.approx(0.5, abs=0.001)
    assert decay(48, Persistence.STRUCTURAL) == pytest.approx(0.25, abs=0.001)


def test_a_transient_contradiction_halves_far_sooner() -> None:
    assert decay(6, Persistence.TRANSIENT) == pytest.approx(0.5, abs=0.001)
    assert half_life(Persistence.TRANSIENT) < half_life(Persistence.STRUCTURAL)


def test_a_missing_lift_outlasts_a_broken_one() -> None:
    at = STAY.plus(18)
    absent = weigh(contradiction(Persistence.STRUCTURAL), at)
    broken = weigh(contradiction(Persistence.TRANSIENT), at)
    assert absent.weight > broken.weight


def test_nothing_decays_below_the_floor() -> None:
    assert decay(600, Persistence.TRANSIENT) == FLOOR
    assert decay(6000, Persistence.STRUCTURAL) == FLOOR
    assert weigh(contradiction(strength=4), STAY.plus(600)).weight == pytest.approx(4 * FLOOR)


def test_decay_never_climbs_as_a_contradiction_ages() -> None:
    for persistence in Persistence:
        seen = [decay(months, persistence) for months in range(0, 120)]
        assert seen == sorted(seen, reverse=True)


def test_a_stronger_rule_weighs_more_at_the_same_age() -> None:
    at = STAY.plus(12)
    assert weigh(contradiction(strength=5), at).weight > weigh(contradiction(strength=2), at).weight


def test_a_kind_with_no_published_half_life_is_refused() -> None:
    with pytest.raises(Invalid, match="no half life"):
        half_life("guesswork")  # type: ignore[arg-type]


def test_the_weighed_contradiction_carries_the_keys_a_case_file_cites() -> None:
    found = weigh(contradiction(), STAY.plus(6))
    assert found.claim_key == "lift"
    assert found.review_key == "seaboard:1"
    assert found.structural
    assert found.line() == f"{found.weight:.2f} after 6 months"


def test_weighing_a_set_puts_the_heaviest_first() -> None:
    found = weigh_all(
        (
            contradiction(strength=2, review_key="seaboard:2"),
            contradiction(strength=5, review_key="seaboard:1"),
            contradiction(strength=4, review_key="seaboard:3"),
        ),
        STAY,
    )
    assert [item.weight for item in found] == [5.0, 4.0, 2.0]


def test_two_contradictions_of_equal_weight_come_back_in_a_stable_order() -> None:
    found = weigh_all(
        (
            contradiction(review_key="seaboard:9"),
            contradiction(review_key="seaboard:1"),
        ),
        STAY,
    )
    assert [item.review_key for item in found] == ["seaboard:1", "seaboard:9"]


def test_weighing_an_empty_set_gives_back_no_weights() -> None:
    assert weigh_all((), STAY) == ()


def test_the_same_evidence_weighs_the_same_however_it_is_ordered() -> None:
    items = (
        contradiction(strength=3, review_key="seaboard:1"),
        contradiction(strength=3, review_key="seaboard:2"),
    )
    at = STAY.plus(7)
    forwards = sum(item.weight for item in weigh_all(items, at))
    backwards = sum(item.weight for item in weigh_all(tuple(reversed(items)), at))
    assert forwards == backwards
