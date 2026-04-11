"""How to find the reviews on one channel, written down rather than coded.

A profile is data. That is the whole point of it. When a channel changes its
templates the fix is a new profile version in the register, not a release of
this package, and the case file can say which profile version read the page it
is quoting.

Every selector is compiled when the profile is built, so a typo is a refusal at
registration rather than a property that quietly has no reviews.
"""

from __future__ import annotations

from dataclasses import dataclass

from tariffpeg.errors import Invalid
from tariffpeg.ids import is_slug
from tariffpeg.parse.select import Selector, compile_selector

FIELD_NAMES = (
    "channel_review_id",
    "title",
    "body",
    "score",
    "stay_month",
    "room_class",
    "reviewer",
    "submitted",
    "response",
    "language",
    "translated_from",
)
"""Every field a profile is allowed to describe."""

REQUIRED_FIELDS = ("channel_review_id", "body", "score")
"""A review with no id, no words and no score is not evidence of anything."""

SOURCES = ("text", "attribute", "structured")
"""Where a field can be read from."""


@dataclass(frozen=True, slots=True)
class FieldRule:
    """How one field is read out of one review block."""

    name: str
    source: str = "text"
    selector: str = ""
    attribute: str = ""
    key: str = ""
    required: bool = False

    def __post_init__(self) -> None:
        if self.name not in FIELD_NAMES:
            raise Invalid("field", self.name, "a profile cannot describe a field nobody reads")
        if self.source not in SOURCES:
            raise Invalid("source", self.source, "a field is read from text, an attribute or json")
        if self.source == "structured":
            if not self.key:
                raise Invalid("key", self.key, "a structured field names the key it reads")
            if self.selector:
                raise Invalid("selector", self.selector, "a structured field has no selector")
            return
        if not self.selector:
            raise Invalid("selector", self.selector, "a markup field names the selector it reads")
        if self.source == "attribute" and not self.attribute:
            raise Invalid("attribute", self.attribute, "an attribute field names the attribute")
        if self.source == "text" and self.attribute:
            raise Invalid("attribute", self.attribute, "a text field does not read an attribute")

    def compiled(self) -> Selector:
        """Return the compiled selector for this rule."""
        if not self.selector:
            raise Invalid("selector", self.name, "this field is read from structured data")
        return compile_selector(self.selector)


@dataclass(frozen=True, slots=True)
class Profile:
    """One version of how a channel is read."""

    channel: str
    version: int
    container: str
    fields: tuple[FieldRule, ...]
    next_page: str = ""
    prefer_structured: bool = False

    def __post_init__(self) -> None:
        if not is_slug(self.channel):
            raise Invalid("channel", self.channel, "a profile belongs to a channel slug")
        if self.version < 1:
            raise Invalid("version", self.version, "profile versions start at one")
        compile_selector(self.container)
        if self.next_page:
            compile_selector(self.next_page)
        seen: set[str] = set()
        for rule in self.fields:
            if rule.name in seen:
                raise Invalid("fields", rule.name, "a field is described once per profile")
            seen.add(rule.name)
            if rule.selector:
                compile_selector(rule.selector)
        missing = [name for name in REQUIRED_FIELDS if name not in seen]
        if missing:
            raise Invalid("fields", missing[0], "this field is required in every profile")

    def rule(self, name: str) -> FieldRule | None:
        """Return the rule for a field, or nothing if the profile omits it."""
        for rule in self.fields:
            if rule.name == name:
                return rule
        return None

    def describes(self, name: str) -> bool:
        """Return whether the profile says how to read this field."""
        return self.rule(name) is not None

    def field_names(self) -> tuple[str, ...]:
        """Return the fields this profile describes, in profile order."""
        return tuple(rule.name for rule in self.fields)

    def markup_rules(self) -> tuple[FieldRule, ...]:
        """Return the rules that read markup rather than structured data."""
        return tuple(rule for rule in self.fields if rule.source != "structured")

    def structured_rules(self) -> tuple[FieldRule, ...]:
        """Return the rules that read structured data."""
        return tuple(rule for rule in self.fields if rule.source == "structured")

    def container_selector(self) -> Selector:
        """Return the compiled selector that finds one review block."""
        return compile_selector(self.container)

    def next_page_selector(self) -> Selector | None:
        """Return the compiled selector for the link to the next page."""
        return compile_selector(self.next_page) if self.next_page else None

    def key(self) -> str:
        """Return the string that names this profile in the ledger."""
        return f"{self.channel}/v{self.version}"
