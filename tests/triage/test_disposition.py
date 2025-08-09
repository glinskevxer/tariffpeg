"""The operator will ask what else was looked at, and the answer has to be more than nothing."""

from __future__ import annotations

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.model.period import Season, StayMonth
from tariffpeg.sample.coverage import Coverage, SeasonCoverage
from tariffpeg.triage.corroborate import Finding
from tariffpeg.triage.disposition import (
    PUBLISHED,
    TAIL_SHARE,
    Decision,
    Disposition,
    Thresholds,
    combine,
    decide,
    heavier,
)
from tariffpeg.triage.weight import Weighed
from tests.triage.conftest import a_weighed

WINDOW = (StayMonth(2024, 7), StayMonth(2026, 6))


def finding(claim_key: str = "breakfast_included", score: float = 8.0) -> Finding:
    """Return a finding that scores a wanted amount, by rigging the weight."""
    weighed: tuple[Weighed, ...] = (a_weighed(claim_key=claim_key, weight=score),)
    return Finding(4021, claim_key, "yes", weighed, 2, ("seaboard", "quayside"))


def scored(claim_key: str, score: float) -> Finding:
    built = finding(claim_key, 1.0)
    wanted = score / built.corroboration
    return Finding(
        4021,
        claim_key,
        "yes",
        (a_weighed(claim_key=claim_key, weight=wanted),),
        2,
        ("seaboard", "quayside"),
    )


def full_coverage(satisfied: bool = True) -> Coverage:
    held = 12 if satisfied else 2
    return Coverage(
        serial=4021,
        seasons=(
            SeasonCoverage(Season.PEAK, 12, held),
            SeasonCoverage(Season.SHOULDER, 0, 0),
            SeasonCoverage(Season.OFF, 0, 0),
        ),
        channels_held=("seaboard", "quayside"),
        channels_wanted=2,
        window=WINDOW,
        opinions=held,
    )


def test_nothing_found_is_no_action() -> None:
    found = decide(4021, [])
    assert found.disposition is Disposition.NO_ACTION
    assert found.score == 0.0
    assert not found.needs_a_visit
    assert found.leading() is None


def test_a_small_finding_is_a_desk_enquiry() -> None:
    found = decide(4021, [scored("breakfast_included", 4.0)], full_coverage())
    assert found.disposition is Disposition.DESK_ENQUIRY
    assert not found.needs_a_visit


def test_a_heavier_finding_earns_a_re_inspection() -> None:
    found = decide(4021, [scored("breakfast_included", 8.0)], full_coverage())
    assert found.disposition is Disposition.REINSPECTION
    assert found.needs_a_visit


def test_a_very_heavy_finding_is_urgent() -> None:
    found = decide(4021, [scored("breakfast_included", 20.0)], full_coverage())
    assert found.disposition is Disposition.URGENT


def test_one_strong_finding_beats_several_weak_ones_that_add_up_the_same() -> None:
    strong = combine([scored("a", 8.0)]) if False else combine([scored("breakfast_included", 8.0)])
    weak = combine([scored("breakfast_included", 2.0), scored("pets_accepted", 6.0)])
    assert strong > weak


def test_the_tail_contributes_only_part_of_its_weight() -> None:
    one = scored("breakfast_included", 6.0)
    two = scored("pets_accepted", 4.0)
    assert combine([one, two]) == pytest.approx(6.0 + TAIL_SHARE * 4.0, abs=0.01)


def test_an_access_finding_escalates_below_the_ordinary_band() -> None:
    ordinary = decide(4021, [scored("breakfast_included", 6.0)], full_coverage())
    access = decide(4021, [scored("lift", 6.0)], full_coverage())
    assert ordinary.disposition is Disposition.DESK_ENQUIRY
    assert access.disposition is Disposition.REINSPECTION
    assert any("access findings" in reason for reason in access.reasons)


def test_a_heavy_access_finding_is_urgent_sooner_than_an_ordinary_one() -> None:
    found = decide(4021, [scored("step_free_entrance", 10.0)], full_coverage())
    assert found.disposition is Disposition.URGENT


def test_an_access_finding_below_its_band_does_not_escalate() -> None:
    found = decide(4021, [scored("lift", 4.0)], full_coverage())
    assert found.disposition is Disposition.DESK_ENQUIRY
    assert not any("access findings" in reason for reason in found.reasons)


def test_a_short_sample_holds_the_disposition_at_a_desk_enquiry() -> None:
    found = decide(4021, [scored("lift", 20.0)], full_coverage(satisfied=False))
    assert found.disposition is Disposition.DESK_ENQUIRY
    assert found.capped
    assert any("held at a desk enquiry" in reason for reason in found.reasons)


def test_a_short_sample_does_not_invent_a_disposition_out_of_nothing() -> None:
    found = decide(4021, [], full_coverage(satisfied=False))
    assert found.disposition is Disposition.NO_ACTION
    assert not found.capped


def test_a_short_sample_leaves_a_desk_enquiry_alone() -> None:
    found = decide(4021, [scored("breakfast_included", 4.0)], full_coverage(satisfied=False))
    assert found.disposition is Disposition.DESK_ENQUIRY
    assert not found.capped


def test_a_decision_with_no_coverage_at_all_is_not_capped() -> None:
    found = decide(4021, [scored("lift", 20.0)])
    assert found.disposition is Disposition.URGENT
    assert not found.capped


def test_the_findings_come_back_heaviest_first() -> None:
    found = decide(
        4021,
        [scored("pets_accepted", 2.0), scored("breakfast_included", 9.0)],
        full_coverage(),
    )
    leading = found.leading()
    assert leading is not None
    assert leading.claim_key == "breakfast_included"


def test_the_reasons_always_say_what_the_evidence_scored() -> None:
    found = decide(4021, [scored("breakfast_included", 4.0)], full_coverage())
    assert found.reasons[0].startswith("the evidence scores")


def test_the_heavier_of_two_dispositions_is_the_one_that_stands() -> None:
    assert heavier(Disposition.NO_ACTION, Disposition.URGENT) is Disposition.URGENT
    assert heavier(Disposition.URGENT, Disposition.DESK_ENQUIRY) is Disposition.URGENT
    assert heavier(Disposition.DESK_ENQUIRY, Disposition.DESK_ENQUIRY) is Disposition.DESK_ENQUIRY


def test_bands_that_do_not_climb_in_order_are_refused() -> None:
    with pytest.raises(Invalid, match="climb from nought in order"):
        Thresholds(desk=9.0, reinspection=3.0)
    with pytest.raises(Invalid, match="access bands climb"):
        Thresholds(access_reinspection=9.0, access_urgent=3.0)


def test_the_published_bands_put_access_ahead_of_the_ordinary_ones() -> None:
    assert PUBLISHED.access_reinspection < PUBLISHED.reinspection
    assert PUBLISHED.access_urgent < PUBLISHED.urgent


def test_a_decision_carries_the_licence_it_is_about() -> None:
    assert Decision(4021, Disposition.NO_ACTION, 0.0, 0.0, (), ()).licence_serial == 4021
