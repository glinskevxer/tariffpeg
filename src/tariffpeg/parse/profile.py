"""Compiling the selectors a profile is written with.

The profile itself is a record and lives in the model, because the store holds
one. What lives here is the part that needs to know what a selector is: turning
the strings on a profile into something that can be run against a page, and
refusing a profile whose selectors will not compile.

Registration goes through :func:`check`, so a typo is a refusal at registration
rather than a property that quietly has no reviews.
"""

from __future__ import annotations

from tariffpeg.errors import Invalid
from tariffpeg.model.profile import FIELD_NAMES, REQUIRED_FIELDS, SOURCES, FieldRule, Profile
from tariffpeg.parse.select import Selector, compile_selector

__all__ = [
    "FIELD_NAMES",
    "REQUIRED_FIELDS",
    "SOURCES",
    "FieldRule",
    "Profile",
    "check",
    "compiled",
    "container_selector",
    "next_page_selector",
]


def compiled(rule: FieldRule) -> Selector:
    """Return the compiled selector for one field rule."""
    if not rule.selector:
        raise Invalid("selector", rule.name, "this field is read from structured data")
    return compile_selector(rule.selector)


def container_selector(profile: Profile) -> Selector:
    """Return the compiled selector that finds one review block."""
    return compile_selector(profile.container)


def next_page_selector(profile: Profile) -> Selector | None:
    """Return the compiled selector for the link to the next page."""
    return compile_selector(profile.next_page) if profile.next_page else None


def check(profile: Profile) -> Profile:
    """Return the profile, having compiled every selector on it."""
    container_selector(profile)
    next_page_selector(profile)
    for rule in profile.fields:
        if rule.selector:
            compile_selector(rule.selector)
    return profile
