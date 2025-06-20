"""A signature computed today has to equal one computed in three years."""

from __future__ import annotations

import pytest

from tariffpeg.dedupe.shingle import (
    SIGNATURE_SLOTS,
    Signature,
    flatten_text,
    jaccard,
    shingles,
)
from tariffpeg.errors import Invalid

ORIGINAL = (
    "The lift was out of order for the whole week we were there and nobody at "
    "the front desk mentioned it when we arrived."
)
TRIMMED = (
    "The lift was out of order for the whole week we were there and nobody at "
    "the front desk mentioned it"
)
DIFFERENT = (
    "Breakfast was not included in the rate we paid and we were charged twelve "
    "pounds each on the last morning."
)


def test_flattening_drops_the_punctuation_and_the_case() -> None:
    assert flatten_text("The LIFT, out of order!") == "the lift out of order"
    assert flatten_text("  spaced   out  ") == "spaced out"


def test_flattening_treats_a_hyphen_as_a_space() -> None:
    assert flatten_text("en-suite") == "en suite"


def test_a_body_breaks_into_overlapping_runs_of_words() -> None:
    runs = shingles("one two three four five six", size=5)
    assert runs == frozenset({"one two three four five", "two three four five six"})


def test_a_body_shorter_than_one_run_is_a_single_run_of_itself() -> None:
    assert shingles("very nice", size=5) == frozenset({"very nice"})
    assert shingles("one two three four five", size=5) == frozenset({"one two three four five"})


def test_a_body_with_no_words_has_no_runs() -> None:
    assert shingles("   ") == frozenset()
    assert shingles("!!!") == frozenset()


def test_a_run_of_no_words_is_refused() -> None:
    with pytest.raises(Invalid, match="one word or more"):
        shingles("anything", size=0)


def test_the_exact_overlap_of_two_identical_bodies_is_one() -> None:
    assert jaccard(shingles(ORIGINAL), shingles(ORIGINAL)) == 1.0


def test_the_exact_overlap_of_two_unrelated_bodies_is_nothing() -> None:
    assert jaccard(shingles(ORIGINAL), shingles(DIFFERENT)) == 0.0


def test_two_empty_bodies_overlap_completely_and_one_empty_one_does_not() -> None:
    assert jaccard(frozenset(), frozenset()) == 1.0
    assert jaccard(shingles(ORIGINAL), frozenset()) == 0.0


def test_a_signature_has_a_fixed_number_of_slots() -> None:
    assert len(Signature.of(ORIGINAL).slots) == SIGNATURE_SLOTS


def test_the_same_body_gives_the_same_signature_every_time() -> None:
    assert Signature.of(ORIGINAL) == Signature.of(ORIGINAL)
    assert Signature.of(ORIGINAL).similarity(Signature.of(ORIGINAL)) == 1.0


def test_case_and_punctuation_do_not_change_a_signature() -> None:
    shouted = ORIGINAL.upper().replace(".", "!!!")
    assert Signature.of(ORIGINAL) == Signature.of(shouted)


def test_a_trimmed_copy_is_recognised_as_nearly_the_same() -> None:
    assert Signature.of(ORIGINAL).similarity(Signature.of(TRIMMED)) > 0.7


def test_an_unrelated_body_is_recognised_as_different() -> None:
    assert Signature.of(ORIGINAL).similarity(Signature.of(DIFFERENT)) < 0.2


def test_the_estimate_is_close_to_the_exact_overlap() -> None:
    exact = jaccard(shingles(ORIGINAL), shingles(TRIMMED))
    estimate = Signature.of(ORIGINAL).similarity(Signature.of(TRIMMED))
    assert abs(exact - estimate) < 0.2


def test_an_empty_body_gives_an_empty_signature() -> None:
    empty = Signature.of("   ")
    assert empty.empty
    assert not Signature.of(ORIGINAL).empty


def test_two_empty_signatures_match_and_an_empty_one_matches_nothing_else() -> None:
    assert Signature.of("").similarity(Signature.of("")) == 1.0
    assert Signature.of("").similarity(Signature.of(ORIGINAL)) == 0.0
    assert Signature.of(ORIGINAL).similarity(Signature.of("")) == 0.0


def test_a_signature_round_trips_through_the_store_form() -> None:
    signature = Signature.of(ORIGINAL)
    assert Signature.decode(signature.encode()) == signature


def test_the_store_form_is_fixed_width_hexadecimal() -> None:
    encoded = Signature.of(ORIGINAL).encode()
    parts = encoded.split(",")
    assert len(parts) == SIGNATURE_SLOTS
    assert all(len(part) == 16 for part in parts)


def test_a_store_form_with_the_wrong_number_of_slots_is_refused() -> None:
    with pytest.raises(Invalid, match="slots"):
        Signature.decode("abc,def")
    with pytest.raises(Invalid, match="slots"):
        Signature((1, 2, 3))


def test_a_store_form_that_is_not_hexadecimal_is_refused() -> None:
    with pytest.raises(Invalid, match="hexadecimal"):
        Signature.decode(",".join(["zzzzzzzzzzzzzzzz"] * SIGNATURE_SLOTS))


def test_the_signature_of_a_known_body_is_stable_across_runs() -> None:
    # Pinned so that a change to the hashing shows up here rather than as a
    # silent change in what counts as a duplicate.
    assert Signature.of("the lift was out of order").encode().startswith("6aba5d765efd01d1")
