"""A number that moves is visible against eleven others that did not."""

from __future__ import annotations

import datetime as dt

from tariffpeg.model.licence import Licence, LicenceStatus
from tariffpeg.model.period import Season, StayMonth
from tariffpeg.report.summary import compile_return
from tariffpeg.sample.coverage import Coverage, SeasonCoverage
from tariffpeg.triage.disposition import Decision, Disposition

AT = StayMonth(2026, 6)
WINDOW = (StayMonth(2024, 7), AT)


def licence(serial: int, status: LicenceStatus = LicenceStatus.ACTIVE) -> Licence:
    return Licence(
        serial=serial,
        trading_name=f"Premises {serial}",
        operator_name="Pellow and Daughter",
        locality="Porthgwarra",
        period_start=dt.date(2025, 1, 1),
        period_end=dt.date(2027, 12, 31),
        particulars={"grading_band": 3, "let_rooms": 9, "bed_spaces": 18},
        status=status,
    )


def coverage(serial: int, satisfied: bool, opinions: int = 12) -> Coverage:
    held = 12 if satisfied else 2
    return Coverage(
        serial=serial,
        seasons=(
            SeasonCoverage(Season.PEAK, 12, held),
            SeasonCoverage(Season.SHOULDER, 0, 0),
            SeasonCoverage(Season.OFF, 0, 0),
        ),
        channels_held=("seaboard", "quayside"),
        channels_wanted=2,
        window=WINDOW,
        opinions=opinions,
    )


def decision(serial: int, disposition: Disposition, capped: bool = False) -> Decision:
    return Decision(serial, disposition, 4.0, 0.0, (), ("because",), capped)


def test_a_month_with_nothing_in_it_counts_nothing() -> None:
    filed = compile_return(AT, [], {}, [])
    assert filed.on_the_register == 0
    assert filed.sampled == 0
    assert filed.needing_a_visit == 0


def test_the_licences_on_the_register_are_counted() -> None:
    filed = compile_return(AT, [licence(1), licence(2)], {}, [])
    assert filed.on_the_register == 2


def test_a_licence_that_is_not_active_is_counted_apart() -> None:
    held = [licence(1), licence(2, LicenceStatus.LAPSED)]
    filed = compile_return(AT, held, {}, [])
    assert filed.on_the_register == 2
    assert filed.active == 1


def test_the_sampled_and_the_short_are_counted_apart() -> None:
    held = [licence(1), licence(2)]
    coverages = {1: coverage(1, True), 2: coverage(2, False)}
    filed = compile_return(AT, held, coverages, [])
    assert filed.sampled == 1
    assert filed.short == 1


def test_the_reviews_still_wanted_are_added_up() -> None:
    coverages = {1: coverage(1, False), 2: coverage(2, False)}
    filed = compile_return(AT, [licence(1), licence(2)], coverages, [])
    assert filed.reviews_short == 20


def test_the_opinions_held_are_added_up() -> None:
    coverages = {1: coverage(1, True, opinions=9), 2: coverage(2, True, opinions=4)}
    filed = compile_return(AT, [licence(1), licence(2)], coverages, [])
    assert filed.opinions == 13


def test_a_licence_nobody_measured_is_not_counted_either_way() -> None:
    filed = compile_return(AT, [licence(1), licence(2)], {1: coverage(1, True)}, [])
    assert filed.sampled == 1
    assert filed.short == 0


def test_every_disposition_is_counted_even_the_ones_at_nothing() -> None:
    found = [decision(1, Disposition.URGENT), decision(2, Disposition.NO_ACTION)]
    filed = compile_return(AT, [licence(1), licence(2)], {}, found)
    assert set(filed.dispositions) == set(Disposition)
    assert filed.dispositions[Disposition.URGENT] == 1
    assert filed.dispositions[Disposition.DESK_ENQUIRY] == 0


def test_the_ones_needing_a_visit_are_the_two_heaviest_bands() -> None:
    found = [
        decision(1, Disposition.URGENT),
        decision(2, Disposition.REINSPECTION),
        decision(3, Disposition.DESK_ENQUIRY),
    ]
    filed = compile_return(AT, [], {}, found)
    assert filed.needing_a_visit == 2


def test_the_ones_held_back_by_a_short_sample_are_counted() -> None:
    found = [
        decision(1, Disposition.DESK_ENQUIRY, capped=True),
        decision(2, Disposition.DESK_ENQUIRY),
    ]
    filed = compile_return(AT, [], {}, found)
    assert filed.held_back == 1


def test_the_return_prints_the_same_figures_every_month() -> None:
    filed = compile_return(AT, [licence(1)], {1: coverage(1, True)}, [])
    figures = [row["figure"] for row in filed.rows()]
    assert figures[0] == "licences on the register"
    assert "held back by a short sample" in figures
    assert len(figures) == 6 + len(Disposition) + 2


def test_the_return_reads_as_lines_with_the_month_at_the_top() -> None:
    lines = compile_return(AT, [licence(1)], {}, []).lines()
    assert lines[0] == "Return for 2026-06"
    assert "licences on the register: 1" in lines
