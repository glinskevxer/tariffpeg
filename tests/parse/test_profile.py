"""A typo in a profile is a refusal at registration, not a property with no reviews."""

from __future__ import annotations

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.model.profile import FieldRule, Profile
from tariffpeg.parse.profile import check, compiled, container_selector, next_page_selector

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


def test_a_profile_whose_selectors_compile_reads_clean() -> None:
    assert check(profile()) is not None


def test_a_container_selector_with_a_typo_is_refused_at_registration() -> None:
    with pytest.raises(Invalid, match="pseudo class is not supported"):
        check(profile(container="article:nth-child(2)"))


def test_a_next_page_selector_with_a_typo_is_refused_too() -> None:
    with pytest.raises(Invalid, match="not a compound"):
        check(profile(next_page="!broken"))


def test_a_field_selector_with_a_typo_is_refused() -> None:
    fields = (*BASE_FIELDS, FieldRule("title", "text", "h3:hover"))
    with pytest.raises(Invalid, match="pseudo class is not supported"):
        check(profile(fields=fields))


def test_the_compiled_selectors_come_back_ready_to_use() -> None:
    built = profile(next_page="a.next")
    assert container_selector(built).branches
    following = next_page_selector(built)
    assert following is not None
    assert following.branches
    assert next_page_selector(profile()) is None


def test_a_structured_rule_has_no_compiled_selector_to_give() -> None:
    rule = FieldRule("title", "structured", key="name")
    with pytest.raises(Invalid, match="read from structured data"):
        compiled(rule)


def test_a_markup_rule_compiles_its_own_selector() -> None:
    assert compiled(FieldRule("body", "text", "p.body")).branches


def test_a_blank_container_is_refused_before_anything_is_compiled() -> None:
    with pytest.raises(Invalid, match="where one review sits"):
        profile(container="   ")
