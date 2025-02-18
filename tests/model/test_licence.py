"""A licence knows its period, its closed season and what the operator signed for."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import Invalid, NotFound
from tariffpeg.model.licence import Licence, LicenceStatus


def make(**over: object) -> Licence:
    base: dict[str, object] = {
        "serial": 4021,
        "trading_name": "The Anchor Rooms",
        "operator_name": "Pellow and Daughter",
        "locality": "Porthgwarra",
        "period_start": dt.date(2025, 4, 1),
        "period_end": dt.date(2026, 3, 31),
        "particulars": {
            "grading_band": 3,
            "let_rooms": 9,
            "bed_spaces": 18,
            "lift": False,
            "shore_distance": 220,
        },
        "closed_months": frozenset({1, 2}),
    }
    base.update(over)
    return Licence(**base)  # type: ignore[arg-type]


def test_the_reference_is_derived_from_the_serial() -> None:
    assert make().ref.startswith("L-004021-")


def test_a_licence_needs_a_trading_name_and_an_operator() -> None:
    with pytest.raises(Invalid, match="trading name"):
        make(trading_name="   ")
    with pytest.raises(Invalid, match="needs an operator"):
        make(operator_name="")


def test_a_period_has_to_end_after_it_starts() -> None:
    with pytest.raises(Invalid, match="ends after it starts"):
        make(period_start=dt.date(2026, 4, 1), period_end=dt.date(2025, 4, 1))


def test_a_closed_month_outside_the_calendar_is_refused() -> None:
    with pytest.raises(Invalid, match="one to twelve"):
        make(closed_months=frozenset({0}))
    with pytest.raises(Invalid, match="one to twelve"):
        make(closed_months=frozenset({13}))


def test_a_premises_closed_every_month_is_not_trading_at_all() -> None:
    with pytest.raises(Invalid, match="not trading"):
        make(closed_months=frozenset(range(1, 13)))


def test_the_three_mandatory_particulars_have_to_be_there() -> None:
    for missing in ("grading_band", "let_rooms", "bed_spaces"):
        particulars = {"grading_band": 3, "let_rooms": 9, "bed_spaces": 18}
        del particulars[missing]
        with pytest.raises(Invalid, match="required on every licence"):
            make(particulars=particulars)


def test_a_particular_outside_the_order_is_refused_at_construction() -> None:
    with pytest.raises(Invalid, match="no such particular"):
        make(particulars={"grading_band": 3, "let_rooms": 9, "bed_spaces": 18, "sauna": True})


def test_a_particular_of_the_wrong_kind_is_refused_at_construction() -> None:
    with pytest.raises(Invalid, match="yes or no"):
        make(particulars={"grading_band": 3, "let_rooms": 9, "bed_spaces": 18, "lift": 1})


def test_a_declared_particular_reads_back_and_an_undeclared_one_raises() -> None:
    licence = make()
    assert licence.declares("lift")
    assert licence.particular("lift") is False
    assert not licence.declares("pets_accepted")
    with pytest.raises(NotFound) as caught:
        licence.particular("pets_accepted")
    assert caught.value.kind == "particular"


def test_asking_for_something_that_is_not_a_particular_at_all_is_a_different_refusal() -> None:
    with pytest.raises(Invalid, match="no such particular"):
        make().particular("helipad")


def test_the_band_comes_back_as_a_number_of_keys() -> None:
    assert make().band() == 3


def test_the_period_covers_its_own_ends() -> None:
    licence = make()
    assert licence.covers(dt.date(2025, 4, 1))
    assert licence.covers(dt.date(2026, 3, 31))
    assert not licence.covers(dt.date(2025, 3, 31))
    assert not licence.covers(dt.date(2026, 4, 1))


def test_a_closed_month_is_reported_as_closed() -> None:
    licence = make()
    assert licence.is_closed_in(1)
    assert not licence.is_closed_in(7)
    with pytest.raises(Invalid, match="one to twelve"):
        licence.is_closed_in(0)


def test_trading_needs_an_active_status_a_covered_day_and_an_open_month() -> None:
    licence = make()
    assert licence.is_trading_on(dt.date(2025, 7, 4))
    assert not licence.is_trading_on(dt.date(2026, 1, 4))
    assert not licence.is_trading_on(dt.date(2024, 7, 4))
    assert not licence.with_status(LicenceStatus.SUSPENDED).is_trading_on(dt.date(2025, 7, 4))
    assert not licence.with_status(LicenceStatus.LAPSED).is_trading_on(dt.date(2025, 7, 4))


def test_the_open_months_are_the_calendar_less_the_closed_ones() -> None:
    assert make().open_months() == (3, 4, 5, 6, 7, 8, 9, 10, 11, 12)
    assert make(closed_months=frozenset()).open_months() == tuple(range(1, 13))


def test_a_variation_returns_a_copy_and_leaves_the_original_alone() -> None:
    licence = make()
    varied = licence.with_particular("lift", True)
    assert varied.particular("lift") is True
    assert licence.particular("lift") is False
    assert varied.serial == licence.serial


def test_a_variation_adds_a_particular_that_was_not_there_before() -> None:
    varied = make().with_particular("pets_accepted", True)
    assert varied.declares("pets_accepted")


def test_a_variation_still_runs_the_kind_check() -> None:
    with pytest.raises(Invalid, match="whole number"):
        make().with_particular("let_rooms", True)


def test_a_status_change_returns_a_copy() -> None:
    licence = make()
    suspended = licence.with_status(LicenceStatus.SUSPENDED)
    assert suspended.status is LicenceStatus.SUSPENDED
    assert licence.status is LicenceStatus.ACTIVE
