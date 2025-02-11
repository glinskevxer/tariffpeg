"""The vocabulary of particulars is fixed by the licensing order."""

from __future__ import annotations

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.model.particulars import (
    BY_KEY,
    SPECS,
    ClaimKind,
    ClaimSpec,
    parse_value,
    spec_for,
)


def test_every_particular_has_a_distinct_key() -> None:
    keys = [spec.key for spec in SPECS]
    assert len(keys) == len(set(keys))
    assert len(BY_KEY) == len(SPECS)


def test_every_particular_has_a_label_that_reads_as_a_sentence() -> None:
    for spec in SPECS:
        assert spec.label
        assert spec.label[0].islower()
        assert " " in spec.label


def test_only_distances_are_allowed_to_be_bounded_on_one_side() -> None:
    for spec in SPECS:
        if spec.upper_only:
            assert spec.kind is ClaimKind.DISTANCE_M


def test_flags_and_bands_carry_no_tolerance() -> None:
    for spec in SPECS:
        if spec.kind in (ClaimKind.FLAG, ClaimKind.BAND):
            assert spec.tolerance == 0


def test_a_key_outside_the_order_is_refused_by_name() -> None:
    with pytest.raises(Invalid, match="no such particular"):
        spec_for("swimming_pool")


def test_a_flag_takes_a_boolean_and_nothing_else() -> None:
    lift = spec_for("lift")
    assert lift.validate(True) is True
    assert lift.validate(False) is False
    with pytest.raises(Invalid, match="yes or no"):
        lift.validate(1)


def test_a_count_refuses_a_boolean_even_though_python_calls_it_an_integer() -> None:
    rooms = spec_for("let_rooms")
    with pytest.raises(Invalid, match="whole number"):
        rooms.validate(True)


def test_a_count_refuses_a_negative_and_accepts_zero() -> None:
    rooms = spec_for("let_rooms")
    assert rooms.validate(0) == 0
    with pytest.raises(Invalid, match="cannot be negative"):
        rooms.validate(-1)


def test_a_band_runs_from_one_key_to_five() -> None:
    band = spec_for("grading_band")
    for keys in (1, 2, 3, 4, 5):
        assert band.validate(keys) == keys
    with pytest.raises(Invalid, match="one to five"):
        band.validate(6)
    with pytest.raises(Invalid, match="one to five"):
        band.validate(0)


def test_the_case_file_renders_each_kind_in_its_own_units() -> None:
    assert spec_for("lift").render(True) == "yes"
    assert spec_for("lift").render(False) == "no"
    assert spec_for("shore_distance").render(400) == "400 m"
    assert spec_for("grading_band").render(3) == "3 keys"
    assert spec_for("let_rooms").render(12) == "12"


def test_a_flag_is_typed_in_the_way_a_person_would_write_it() -> None:
    for text in ("yes", "Y", " TRUE ", "1"):
        assert parse_value("lift", text) is True
    for text in ("no", "N", "false", "0"):
        assert parse_value("lift", text) is False
    with pytest.raises(Invalid, match="write yes or no"):
        parse_value("lift", "maybe")


def test_a_distance_can_be_typed_with_or_without_its_unit() -> None:
    assert parse_value("shore_distance", "400") == 400
    assert parse_value("shore_distance", "400m") == 400
    assert parse_value("shore_distance", " 400 M ") == 400


def test_a_band_can_be_typed_with_the_word_keys_after_it() -> None:
    assert parse_value("grading_band", "3") == 3
    assert parse_value("grading_band", "3 keys") == 3


def test_something_that_is_not_a_number_is_refused_with_the_field_named() -> None:
    with pytest.raises(Invalid) as caught:
        parse_value("bed_spaces", "a dozen")
    assert caught.value.field == "bed_spaces"
    assert "whole number" in caught.value.reason


def test_parsing_still_runs_the_range_check_for_the_kind() -> None:
    with pytest.raises(Invalid, match="one to five"):
        parse_value("grading_band", "9")
    with pytest.raises(Invalid, match="cannot be negative"):
        parse_value("parking_spaces", "-2")


def test_a_spec_is_frozen_so_a_caller_cannot_widen_a_tolerance() -> None:
    spec = spec_for("bed_spaces")
    with pytest.raises(AttributeError):
        spec.tolerance = 50  # type: ignore[misc]


def test_the_specs_tuple_and_the_index_agree_on_every_entry() -> None:
    for spec in SPECS:
        assert BY_KEY[spec.key] is spec
        assert isinstance(spec, ClaimSpec)
