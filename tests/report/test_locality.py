"""A locality where nothing is sampled is a resourcing conversation, not a standards one."""

from __future__ import annotations

import datetime as dt

from tariffpeg.model.licence import Licence, LicenceStatus
from tariffpeg.model.period import Season, StayMonth
from tariffpeg.report.locality import by_locality, unsampled
from tariffpeg.sample.coverage import Coverage, SeasonCoverage
from tariffpeg.triage.disposition import Decision, Disposition

AT = StayMonth(2026, 6)
WINDOW = (StayMonth(2024, 7), AT)


def licence(serial: int, locality: str, status: LicenceStatus = LicenceStatus.ACTIVE) -> Licence:
    return Licence(
        serial=serial,
        trading_name=f"Premises {serial}",
        operator_name="Pellow and Daughter",
        locality=locality,
        period_start=dt.date(2025, 1, 1),
        period_end=dt.date(2027, 12, 31),
        particulars={"grading_band": 3, "let_rooms": 9, "bed_spaces": 18},
        status=status,
    )


def coverage(serial: int, satisfied: bool) -> Coverage:
    held = 12 if satisfied else 2
    return Coverage(
        serial=serial,
        seasons=(SeasonCoverage(Season.PEAK, 12, held),),
        channels_held=("seaboard", "quayside"),
        channels_wanted=2,
        window=WINDOW,
        opinions=held,
    )


def decision(serial: int, disposition: Disposition) -> Decision:
    return Decision(serial, disposition, 4.0, 0.0, (), ("because",))


def test_a_register_with_nothing_on_it_breaks_down_into_nothing() -> None:
    assert by_locality([], {}, []) == ()


def test_each_locality_gets_one_entry_in_alphabetical_order() -> None:
    held = [licence(1, "Sennen"), licence(2, "Porthgwarra"), licence(3, "Sennen")]
    places = by_locality(held, {}, [])
    assert [place.locality for place in places] == ["Porthgwarra", "Sennen"]
    assert [place.licences for place in places] == [1, 2]


def test_a_licence_that_is_not_active_is_left_out() -> None:
    held = [licence(1, "Sennen"), licence(2, "Sennen", LicenceStatus.LAPSED)]
    assert by_locality(held, {}, [])[0].licences == 1


def test_the_sampled_and_the_short_are_counted_in_each_locality() -> None:
    held = [licence(1, "Sennen"), licence(2, "Sennen")]
    coverages = {1: coverage(1, True), 2: coverage(2, False)}
    place = by_locality(held, coverages, [])[0]
    assert place.sampled == 1
    assert place.short == 1


def test_the_visits_needed_are_counted_in_each_locality() -> None:
    held = [licence(1, "Sennen"), licence(2, "Sennen")]
    found = [decision(1, Disposition.URGENT), decision(2, Disposition.DESK_ENQUIRY)]
    assert by_locality(held, {}, found)[0].needing_a_visit == 1


def test_the_worst_disposition_in_a_locality_is_the_heaviest_one() -> None:
    held = [licence(1, "Sennen"), licence(2, "Sennen")]
    found = [decision(1, Disposition.DESK_ENQUIRY), decision(2, Disposition.REINSPECTION)]
    assert by_locality(held, {}, found)[0].worst is Disposition.REINSPECTION


def test_a_locality_with_no_decisions_reads_as_no_action() -> None:
    assert by_locality([licence(1, "Sennen")], {}, [])[0].worst is Disposition.NO_ACTION


def test_a_locality_where_nothing_is_sampled_says_so() -> None:
    held = [licence(1, "Sennen"), licence(2, "Porthgwarra")]
    coverages = {1: coverage(1, False), 2: coverage(2, True)}
    places = by_locality(held, coverages, [])
    assert unsampled(places) == ("Sennen",)


def test_a_locality_nobody_has_measured_does_not_read_as_unsampled() -> None:
    places = by_locality([licence(1, "Sennen")], {}, [])
    assert places[0].sampled == 0
    assert places[0].nothing_sampled


def test_a_locality_with_no_licences_is_not_reported_as_unsampled() -> None:
    from tariffpeg.report.locality import Place

    empty = Place("Nowhere", 0, 0, 0, 0, Disposition.NO_ACTION)
    assert not empty.nothing_sampled


def test_the_row_a_locality_prints_carries_every_figure() -> None:
    row = by_locality([licence(1, "Sennen")], {1: coverage(1, True)}, [])[0].row()
    assert row["locality"] == "Sennen"
    assert row["licences"] == 1
    assert row["sampled"] == 1
    assert row["worst"] == "no action"
