"""A typo in a profile is a refusal at registration, not a property with no reviews."""

from __future__ import annotations

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.parse.profile import FieldRule, Profile

BASE_FIELDS = (
    FieldRule("channel_review_id", "attribute", "article.review", "data-id", required=True),
    FieldRule("body", "text", "p.body", required=True),
    FieldRule("score", "attribute", "span.score", "data-value", required=True),
)


def profile(**over: object) -> Profile:
    base: dict[str, object] = {
        "channel": "seaboard",
        "version": 1,
        "container": "article.review",
        "fields": BASE_FIELDS,
    }
    base.update(over)
    return Profile(**base)  # type: ignore[arg-type]


def test_a_profile_names_itself_for_the_ledger() -> None:
    assert profile().key() == "seaboard/v1"
    assert profile(version=4).key() == "seaboard/v4"


def test_a_profile_belongs_to_a_channel_slug() -> None:
    with pytest.raises(Invalid, match="channel slug"):
        profile(channel="Seaboard Stays")


def test_profile_versions_start_at_one() -> None:
    with pytest.raises(Invalid, match="start at one"):
        profile(version=0)


def test_a_container_selector_with_a_typo_is_refused_at_registration() -> None:
    with pytest.raises(Invalid, match="pseudo class is not supported"):
        profile(container="article:nth-child(2)")


def test_a_next_page_selector_with_a_typo_is_refused_too() -> None:
    with pytest.raises(Invalid, match="not a compound"):
        profile(next_page="!broken")


def test_a_field_selector_with_a_typo_is_refused() -> None:
    fields = (*BASE_FIELDS, FieldRule("title", "text", "h3:hover"))
    with pytest.raises(Invalid, match="pseudo class is not supported"):
        profile(fields=fields)


def test_a_field_nobody_reads_is_refused() -> None:
    with pytest.raises(Invalid, match="a field nobody reads"):
        FieldRule("mood", "text", "p.mood")


def test_a_source_that_is_not_one_of_the_three_is_refused() -> None:
    with pytest.raises(Invalid, match="text, an attribute or json"):
        FieldRule("title", "guess", "h3")


def test_a_markup_field_has_to_name_its_selector() -> None:
    with pytest.raises(Invalid, match="names the selector"):
        FieldRule("title", "text")


def test_an_attribute_field_has_to_name_its_attribute() -> None:
    with pytest.raises(Invalid, match="names the attribute"):
        FieldRule("title", "attribute", "h3")


def test_a_text_field_that_also_names_an_attribute_is_refused() -> None:
    with pytest.raises(Invalid, match="does not read an attribute"):
        FieldRule("title", "text", "h3", "data-title")


def test_a_structured_field_names_a_key_and_no_selector() -> None:
    rule = FieldRule("title", "structured", key="name")
    assert rule.key == "name"
    with pytest.raises(Invalid, match="names the key"):
        FieldRule("title", "structured")
    with pytest.raises(Invalid, match="has no selector"):
        FieldRule("title", "structured", "h3", key="name")


def test_a_field_described_twice_is_refused() -> None:
    fields = (*BASE_FIELDS, FieldRule("body", "text", "div.body"))
    with pytest.raises(Invalid, match="described once"):
        profile(fields=fields)


def test_the_three_required_fields_have_to_be_described() -> None:
    for index in range(3):
        fields = tuple(rule for pos, rule in enumerate(BASE_FIELDS) if pos != index)
        with pytest.raises(Invalid, match="required in every profile"):
            profile(fields=fields)


def test_a_profile_says_which_fields_it_describes() -> None:
    built = profile()
    assert built.field_names() == ("channel_review_id", "body", "score")
    assert built.describes("body")
    assert not built.describes("room_class")
    assert built.rule("room_class") is None
    rule = built.rule("body")
    assert rule is not None
    assert rule.selector == "p.body"


def test_markup_rules_and_structured_rules_are_kept_apart() -> None:
    fields = (*BASE_FIELDS, FieldRule("title", "structured", key="name"))
    built = profile(fields=fields)
    assert [rule.name for rule in built.markup_rules()] == [
        "channel_review_id",
        "body",
        "score",
    ]
    assert [rule.name for rule in built.structured_rules()] == ["title"]


def test_the_compiled_selectors_come_back_ready_to_use() -> None:
    built = profile(next_page="a.next")
    assert built.container_selector().branches
    following = built.next_page_selector()
    assert following is not None
    assert following.branches
    assert profile().next_page_selector() is None


def test_a_structured_rule_has_no_compiled_selector_to_give() -> None:
    rule = FieldRule("title", "structured", key="name")
    with pytest.raises(Invalid, match="read from structured data"):
        rule.compiled()


def test_a_markup_rule_compiles_its_own_selector() -> None:
    rule = FieldRule("body", "text", "p.body")
    assert rule.compiled().branches


def test_a_profile_can_say_it_prefers_the_structured_copy() -> None:
    assert not profile().prefer_structured
    assert profile(prefer_structured=True).prefer_structured
