"""A selector with a typo in it raises, because silence looks like no reviews."""

from __future__ import annotations

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.parse.dom import parse
from tariffpeg.parse.select import compile_selector

PAGE = """
<div id="reviews" class="panel wide" data-count="3">
  <article class="review" data-id="91188" lang="en-GB">
    <h3 class="title">Lovely spot</h3>
    <p class="body">The lift was out all week.</p>
    <span class="score" data-value="8.4">8.4</span>
  </article>
  <article class="review featured" data-id="91190" lang="fr">
    <h3 class="title">Bien</h3>
    <p class="body">Pas de petit dejeuner.</p>
    <span class="score" data-value="6.0">6.0</span>
  </article>
  <article class="review" data-id="91191">
    <h3 class="title">Fine</h3>
    <p class="body"></p>
  </article>
</div>
"""


def picked(selector: str) -> list[str]:
    root = parse(PAGE)
    return [node.tag for node in compile_selector(selector).select(root)]


def test_a_tag_name_picks_every_element_with_that_tag() -> None:
    assert picked("article") == ["article", "article", "article"]


def test_the_universal_selector_picks_everything() -> None:
    assert len(picked("*")) == len(parse(PAGE).descendants())


def test_a_class_picks_the_elements_carrying_it() -> None:
    assert len(picked(".review")) == 3
    assert picked(".featured") == ["article"]


def test_two_classes_together_mean_both() -> None:
    assert len(picked(".review.featured")) == 1
    assert picked(".review.missing") == []


def test_an_id_picks_the_one_element() -> None:
    assert picked("#reviews") == ["div"]
    assert picked("#nothing") == []


def test_a_tag_and_a_class_together_narrow_each_other() -> None:
    assert len(picked("article.review")) == 3
    assert picked("p.review") == []


def test_an_attribute_test_with_no_operator_asks_only_whether_it_is_there() -> None:
    assert len(picked("[data-id]")) == 3
    assert picked("[data-count]") == ["div"]


def test_an_attribute_equals_test_compares_the_whole_value() -> None:
    root = parse(PAGE)
    found = compile_selector('[data-id="91190"]').select(root)
    assert len(found) == 1
    assert found[0].get("lang") == "fr"


def test_an_attribute_value_may_be_written_with_apostrophes() -> None:
    root = parse(PAGE)
    assert len(compile_selector("[data-id='91188']").select(root)) == 1


def test_an_attribute_value_may_be_written_bare() -> None:
    root = parse(PAGE)
    assert len(compile_selector("[data-id=91188]").select(root)) == 1


def test_the_prefix_and_suffix_and_contains_tests_do_what_they_say() -> None:
    root = parse(PAGE)
    assert len(compile_selector('[data-id^="9119"]').select(root)) == 2
    assert len(compile_selector('[data-id$="0"]').select(root)) == 1
    assert len(compile_selector('[data-id*="118"]').select(root)) == 1


def test_an_empty_value_never_matches_a_prefix_or_suffix_or_contains_test() -> None:
    root = parse(PAGE)
    assert compile_selector('[data-id^=""]').select(root) == ()
    assert compile_selector('[data-id$=""]').select(root) == ()
    assert compile_selector('[data-id*=""]').select(root) == ()


def test_the_word_test_looks_inside_a_space_separated_list() -> None:
    root = parse(PAGE)
    assert len(compile_selector('[class~="featured"]').select(root)) == 1
    assert compile_selector('[class~="wid"]').select(root) == ()


def test_the_language_test_matches_a_value_or_that_value_with_a_region_after_it() -> None:
    root = parse(PAGE)
    assert len(compile_selector('[lang|="en"]').select(root)) == 1
    assert len(compile_selector('[lang|="fr"]').select(root)) == 1
    assert compile_selector('[lang|="e"]').select(root) == ()


def test_a_descendant_selector_reaches_any_depth() -> None:
    assert len(picked("#reviews .title")) == 3
    assert len(picked("div span")) == 2


def test_a_child_selector_only_reaches_one_level() -> None:
    assert len(picked("#reviews > article")) == 3
    assert picked("#reviews > .title") == []


def test_an_adjacent_sibling_selector_looks_at_the_element_just_before() -> None:
    assert len(picked("h3 + p")) == 3
    assert len(picked("p + span")) == 2
    assert picked("h3 + span") == []


def test_first_and_last_and_only_child_count_elements_and_not_text() -> None:
    assert picked("article:first-child") == ["article"]
    assert picked("article:last-child") == ["article"]
    assert len(picked("h3:first-child")) == 3
    assert picked("article:only-child") == []
    assert picked("div:only-child") == ["div"]


def test_nth_of_type_counts_within_the_same_tag() -> None:
    root = parse(PAGE)
    second = compile_selector("article:nth-of-type(2)").select(root)
    assert len(second) == 1
    assert second[0].get("data-id") == "91190"
    assert compile_selector("article:nth-of-type(9)").select(root) == ()


def test_not_empty_skips_the_element_with_nothing_written_in_it() -> None:
    assert len(picked("p.body:not-empty")) == 2


def test_a_comma_separated_list_is_the_union_of_its_branches() -> None:
    assert len(picked("h3, span")) == 5


def test_the_first_match_can_be_asked_for_on_its_own() -> None:
    root = parse(PAGE)
    first = compile_selector("article").first(root)
    assert first is not None
    assert first.get("data-id") == "91188"
    assert compile_selector("table").first(root) is None


def test_matching_can_be_asked_of_one_element() -> None:
    root = parse(PAGE)
    article = compile_selector("article").first(root)
    assert article is not None
    assert compile_selector(".review").matches(article)
    assert not compile_selector(".featured").matches(article)


def test_a_blank_selector_is_refused() -> None:
    with pytest.raises(Invalid, match="cannot be blank"):
        compile_selector("   ")
    with pytest.raises(Invalid, match="cannot be blank"):
        compile_selector("article,")


def test_a_selector_that_starts_or_ends_with_a_combinator_is_refused() -> None:
    with pytest.raises(Invalid, match="cannot start with a combinator"):
        compile_selector("> article")
    with pytest.raises(Invalid, match="cannot end with a combinator"):
        compile_selector("article >")


def test_an_unsupported_pseudo_class_is_refused_rather_than_matching_nothing() -> None:
    with pytest.raises(Invalid, match="pseudo class is not supported"):
        compile_selector("article:nth-child(2)")


def test_nth_of_type_without_a_number_is_refused() -> None:
    with pytest.raises(Invalid, match="takes a number"):
        compile_selector("article:nth-of-type()")


def test_nth_of_type_with_a_word_in_it_is_refused_when_it_is_used() -> None:
    selector = compile_selector("article:nth-of-type(odd)")
    with pytest.raises(Invalid, match="takes a number"):
        selector.select(parse(PAGE))


def test_a_compound_the_reader_does_not_understand_is_refused() -> None:
    with pytest.raises(Invalid, match="not a compound"):
        compile_selector("!broken")


def test_the_compiled_shapes_are_the_ones_the_reader_builds() -> None:
    from tariffpeg.parse.select import AttributeTest, Selector, Simple, Step

    selector = compile_selector('article.review[data-id="1"]')
    assert isinstance(selector, Selector)
    step = selector.branches[0][0]
    assert isinstance(step, Step)
    assert isinstance(step.simple, Simple)
    assert step.simple.tag == "article"
    assert step.simple.classes == ("review",)
    assert step.simple.attributes == (AttributeTest("data-id", "=", "1"),)
