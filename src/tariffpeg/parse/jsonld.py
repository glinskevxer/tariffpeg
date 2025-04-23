"""Reading the structured data channels bury in a script tag.

Most channels publish their reviews twice: once as markup for a person and once
as schema.org objects for a search engine. The second copy is far more stable
than the first, so it is tried before the selectors are. It is not trusted more,
though. A channel that publishes a rounded score in its markup and an unrounded
one here has to be read one way or the other, and the profile says which.

Nothing here raises on bad input. A script block that will not parse is skipped
and named, because one broken block on a page is not a reason to lose the other
four.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from tariffpeg.parse.dom import Element
from tariffpeg.parse.select import compile_selector

SCRIPT = compile_selector('script[type="application/ld+json"]')
"""Where the structured data sits on every channel we read."""

REVIEW_TYPES = frozenset({"Review", "UserReview", "CriticReview"})
"""The schema.org types that carry one guest opinion."""


@dataclass(frozen=True, slots=True)
class Block:
    """One script block, parsed or not."""

    index: int
    objects: tuple[dict[str, Any], ...] = ()
    problem: str = ""

    @property
    def ok(self) -> bool:
        """Return whether the block parsed."""
        return not self.problem


@dataclass(slots=True)
class Structured:
    """Everything the structured data on a page had to say."""

    blocks: tuple[Block, ...] = ()
    _flat: list[dict[str, Any]] = field(default_factory=list)

    def problems(self) -> tuple[str, ...]:
        """Return what could not be read, one line per block."""
        return tuple(block.problem for block in self.blocks if block.problem)

    def objects(self) -> tuple[dict[str, Any], ...]:
        """Return every object found, flattened out of graphs and lists."""
        return tuple(self._flat)

    def of_type(self, wanted: str) -> tuple[dict[str, Any], ...]:
        """Return the objects declaring this schema.org type."""
        return tuple(obj for obj in self._flat if wanted in types_of(obj))

    def reviews(self) -> tuple[dict[str, Any], ...]:
        """Return every review object, wherever on the page it was nested."""
        return tuple(obj for obj in self._flat if types_of(obj) & REVIEW_TYPES)


def types_of(obj: dict[str, Any]) -> frozenset[str]:
    """Return the schema.org types on an object, which may be a list."""
    raw = obj.get("@type")
    if isinstance(raw, str):
        return frozenset({raw})
    if isinstance(raw, list):
        return frozenset(str(item) for item in raw if isinstance(item, str))
    return frozenset()


def text_of(value: Any) -> str:
    """Return a schema.org value as text, unwrapping the shapes channels use."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, dict):
        for key in ("name", "@value", "value", "text"):
            if key in value:
                return text_of(value[key])
        return ""
    if isinstance(value, list):
        for item in value:
            found = text_of(item)
            if found:
                return found
    return ""


def _flatten(value: Any, into: list[dict[str, Any]]) -> None:
    if isinstance(value, list):
        for item in value:
            _flatten(item, into)
        return
    if not isinstance(value, dict):
        return
    into.append(value)
    for key, nested in value.items():
        if key.startswith("@") and key != "@graph":
            continue
        _flatten(nested, into)


def read(root: Element) -> Structured:
    """Read every structured data block on a page."""
    blocks: list[Block] = []
    flat: list[dict[str, Any]] = []
    for index, script in enumerate(SCRIPT.select(root)):
        raw = script.text()
        if not raw.strip():
            blocks.append(Block(index, problem=f"block {index} is empty"))
            continue
        try:
            loaded = json.loads(raw)
        except ValueError as err:
            blocks.append(Block(index, problem=f"block {index} is not json: {err.args[0]}"))
            continue
        found: list[dict[str, Any]] = []
        _flatten(loaded, found)
        blocks.append(Block(index, tuple(found)))
        flat.extend(found)
    return Structured(tuple(blocks), flat)
