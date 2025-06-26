"""A rule an inspector can read back in a hearing bundle."""

from __future__ import annotations

import pytest

from tariffpeg.claims.grammar import (
    Choice,
    Gap,
    Literal,
    Match,
    Maybe,
    Number,
    compile_pattern,
    tokens_of,
)
from tariffpeg.errors import Invalid


def test_text_breaks_into_lowercase_words_with_no_punctuation() -> None:
    assert tokens_of("The lift, out of order!") == ("the", "lift", "out", "of", "order")
    assert tokens_of("Room 12 was fine.") == ("room", "12", "was", "fine")
    assert tokens_of("   ") == ()


def test_a_literal_phrase_matches_those_words_in_that_order() -> None:
    pattern = compile_pattern("out of order")
    assert pattern.matches("The lift was out of order all week.")
    assert not pattern.matches("The lift was out of service all week.")
    assert not pattern.matches("Order of the day was out.")


def test_a_choice_matches_any_of_its_options() -> None:
    pattern = compile_pattern("(out of order|not working|broken)")
    for body in ("it was out of order", "it was not working", "it was broken"):
        assert pattern.matches(body), body
    assert not pattern.matches("it was fine")


def test_a_choice_option_can_be_several_words_long() -> None:
    pattern = compile_pattern("(there is no|they have no) lift")
    assert pattern.matches("There is no lift in the building.")
    assert pattern.matches("They have no lift at all.")


def test_an_optional_word_matches_with_or_without_it() -> None:
    pattern = compile_pattern("the? lift")
    assert pattern.matches("the lift was out")
    assert pattern.matches("no lift here")


def test_a_gap_jumps_over_words_the_rule_does_not_care_about() -> None:
    pattern = compile_pattern("no ... lift")
    assert pattern.matches("there was no working passenger lift")
    assert pattern.matches("no lift")


def test_a_gap_does_not_jump_further_than_it_is_allowed() -> None:
    pattern = compile_pattern("no ... lift")
    assert not pattern.matches("no we did not use the very small lift")


def test_a_number_is_matched_and_captured() -> None:
    pattern = compile_pattern("only # rooms")
    found = pattern.find("There were only 4 rooms let that week.")
    assert found is not None
    assert found.numbers == (4,)


def test_a_number_term_does_not_match_a_word() -> None:
    assert not compile_pattern("only # rooms").matches("only four rooms")


def test_a_match_reports_where_it_landed_in_the_text() -> None:
    tokens = tokens_of("The lift was out of order all week.")
    found = compile_pattern("out of order").find("The lift was out of order all week.")
    assert found is not None
    assert found.span(tokens) == "out of order"
    assert found.start == 3
    assert found.end == 6


def test_a_pattern_that_matches_nothing_returns_nothing() -> None:
    assert compile_pattern("out of order").find("Breakfast was lovely.") is None


def test_every_place_a_pattern_matches_can_be_asked_for() -> None:
    pattern = compile_pattern("(lift|elevator)")
    found = pattern.find_all("The lift was out and the elevator was out too.")
    assert len(found) == 2


def test_matches_do_not_overlap_each_other() -> None:
    pattern = compile_pattern("a a")
    assert len(pattern.find_all("a a a a")) == 2


def test_a_pattern_of_several_terms_matches_them_in_order() -> None:
    pattern = compile_pattern("(no|not) ... (lift|elevator) ... (working|order)")
    assert pattern.matches("There was no lift in working condition at all.")
    assert not pattern.matches("The lift was working, there was no hot water.")


def test_a_blank_pattern_is_refused() -> None:
    with pytest.raises(Invalid, match="cannot be blank"):
        compile_pattern("   ")


def test_a_choice_with_one_option_is_refused() -> None:
    with pytest.raises(Invalid, match="at least two options"):
        compile_pattern("(lift)")


def test_brackets_that_do_not_pair_up_are_refused() -> None:
    with pytest.raises(Invalid, match="no closing one"):
        compile_pattern("(lift|elevator")
    with pytest.raises(Invalid, match="no opening one"):
        compile_pattern("lift|elevator)")


def test_making_more_than_one_word_optional_is_refused() -> None:
    with pytest.raises(Invalid, match="single word"):
        compile_pattern("the-lift?")


def test_a_space_before_the_question_mark_makes_two_terms_and_not_one() -> None:
    pattern = compile_pattern("the lift?")
    assert [type(term).__name__ for term in pattern.terms] == ["Literal", "Maybe"]


def test_a_term_with_no_words_in_it_is_refused() -> None:
    with pytest.raises(Invalid, match="no words in it"):
        compile_pattern("!!!")


def test_the_source_is_kept_so_a_bundle_can_print_the_rule() -> None:
    pattern = compile_pattern("  no   ...   lift  ")
    assert pattern.source == "no ... lift"


def test_the_terms_compile_to_the_shapes_they_say_they_are() -> None:
    pattern = compile_pattern("no? (a|b) ... # lift")
    kinds = [type(term).__name__ for term in pattern.terms]
    assert kinds == ["Maybe", "Choice", "Gap", "Number", "Literal"]
    assert pattern.terms[0] == Maybe("no")
    assert pattern.terms[1] == Choice((("a",), ("b",)))
    assert pattern.terms[2] == Gap()
    assert pattern.terms[3] == Number()
    assert pattern.terms[4] == Literal(("lift",))


def test_a_match_with_no_numbers_captures_nothing() -> None:
    assert Match(0, 3).numbers == ()
