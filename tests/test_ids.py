"""Licence references get read down a telephone, so the check character earns its place."""

from __future__ import annotations

import pytest

from tariffpeg.ids import (
    capture_digest,
    format_licence_ref,
    is_licence_ref,
    is_slug,
    licence_check_character,
    normalise_slug,
    parse_licence_ref,
    review_key,
)


def test_a_reference_round_trips_through_its_own_parser() -> None:
    for serial in (0, 1, 42, 999999, 123456):
        assert parse_licence_ref(format_licence_ref(serial)) == serial


def test_the_printed_form_is_the_prefix_six_digits_and_a_letter() -> None:
    assert format_licence_ref(42).startswith("L-000042-")
    assert len(format_licence_ref(42)) == len("L-000042-X")


SERIALS = (0, 7, 481902, 100000, 999999, 505050, 123456, 246813)


def test_a_single_wrong_digit_changes_the_check_character() -> None:
    for base in SERIALS:
        printed = f"{base:06d}"
        for position in range(6):
            for replacement in "0123456789":
                if replacement == printed[position]:
                    continue
                other = int(printed[:position] + replacement + printed[position + 1 :])
                assert licence_check_character(other) != licence_check_character(base)


def test_swapping_two_neighbouring_digits_changes_the_check_character() -> None:
    for base in SERIALS:
        printed = f"{base:06d}"
        for position in range(5):
            if printed[position] == printed[position + 1]:
                continue
            swapped = (
                printed[:position]
                + printed[position + 1]
                + printed[position]
                + printed[position + 2 :]
            )
            assert licence_check_character(int(swapped)) != licence_check_character(base)


def test_the_check_alphabet_holds_no_vowels() -> None:
    seen = {licence_check_character(n) for n in range(0, 400)}
    assert seen
    assert not seen & set("AEIOU")


def test_a_reference_typed_in_lower_case_with_spaces_still_parses() -> None:
    ref = format_licence_ref(7788)
    assert parse_licence_ref(f"  {ref.lower()} ") == 7788


def test_a_reference_with_the_wrong_check_character_is_refused() -> None:
    ref = format_licence_ref(1234)
    wrong = ref[:-1] + ("Z" if ref[-1] != "Z" else "B")
    with pytest.raises(ValueError, match="check character"):
        parse_licence_ref(wrong)
    assert not is_licence_ref(wrong)


def test_something_that_is_not_shaped_like_a_reference_is_refused() -> None:
    for bad in ("", "L-42-B", "X-000042-B", "L-0000042-B", "000042-B"):
        assert not is_licence_ref(bad)
    with pytest.raises(ValueError, match="shaped like"):
        parse_licence_ref("hello")


def test_a_serial_outside_six_digits_has_no_check_character() -> None:
    with pytest.raises(ValueError, match="6 digits"):
        licence_check_character(1000000)
    with pytest.raises(ValueError, match="6 digits"):
        licence_check_character(-1)


def test_a_name_typed_by_the_unit_becomes_a_slug() -> None:
    assert normalise_slug("Seaboard Rooms") == "seaboard-rooms"
    assert normalise_slug("  HARBOUR / QUAY  ") == "harbour-quay"
    assert normalise_slug("twin_en-suite") == "twin-en-suite"


def test_a_slug_cannot_start_with_a_digit_or_be_empty() -> None:
    with pytest.raises(ValueError, match="starting with a digit"):
        normalise_slug("2 star")
    with pytest.raises(ValueError, match="nothing in it"):
        normalise_slug("   ///  ")


def test_the_slug_test_agrees_with_the_normaliser() -> None:
    for value in ("Seaboard Rooms", "harbour quay", "a"):
        assert is_slug(normalise_slug(value))
    assert not is_slug("Seaboard Rooms")
    assert not is_slug("-leading")
    assert not is_slug("trailing-")


def test_a_capture_digest_keeps_its_algorithm_prefix() -> None:
    digest = capture_digest(b"<html></html>")
    assert digest.startswith("sha256:")
    assert len(digest) == len("sha256:") + 64
    assert capture_digest(b"") != digest


def test_a_review_key_carries_the_channel_because_channels_reuse_numbers() -> None:
    assert review_key("seaboard", "  91188 ") == "seaboard:91188"
    assert review_key("harbour-quay", "91188") != review_key("seaboard", "91188")


def test_a_review_key_refuses_a_blank_id_or_a_name_that_is_not_a_slug() -> None:
    with pytest.raises(ValueError, match="channel slug"):
        review_key("Seaboard", "1")
    with pytest.raises(ValueError, match="blank"):
        review_key("seaboard", "   ")
