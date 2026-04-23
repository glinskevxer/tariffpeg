"""How to find the reviews on one channel, as a record rather than as code.

A profile is data. That is the whole point of it: when a channel changes its
templates the fix is a new version in the register, not a release of this
package, and the case file can say which profile version read the page it is
quoting.

What is checked here is the shape. That every field is one the reader knows,
that a markup field names a selector and a structured one names a key, that the
three required fields are there. Whether the selectors actually compile is
checked in the parse layer, which is the layer that knows what a selector is.
"""

from __future__ import annotations

from dataclasses import dataclass

from tariffpeg.errors import Invalid
from tariffpeg.ids import is_slug

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
        if not self.container.strip():
            raise Invalid("container", self.container, "a profile says where one review sits")
        seen: set[str] = set()
        for rule in self.fields:
            if rule.name in seen:
                raise Invalid("fields", rule.name, "a field is described once per profile")
            seen.add(rule.name)
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

    def key(self) -> str:
        """Return the string that names this profile in the ledger."""
        return f"{self.channel}/v{self.version}"
