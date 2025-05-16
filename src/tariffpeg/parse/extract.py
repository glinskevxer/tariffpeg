"""Applying a profile to a page and getting reviews out of it.

The structured copy of a review is steadier than the markup copy, so a profile
can say it prefers it. Preferring it is not the same as trusting it blindly.
The two copies are matched up by the channel review id where both give one, and
by position only when the counts agree exactly. A structured block that cannot
be matched is left alone and said so, because guessing which markup block a
loose review object belongs to is how a quotation ends up under the wrong
licence.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urljoin

from tariffpeg.parse.dom import Element
from tariffpeg.parse.jsonld import Structured, read, text_of
from tariffpeg.parse.profile import REQUIRED_FIELDS, FieldRule, Profile


@dataclass(frozen=True, slots=True)
class RawReview:
    """One review as it came off a page, before anything is normalised."""

    fields: Mapping[str, str]
    profile_key: str
    position: int = 0

    def get(self, name: str, default: str = "") -> str:
        """Return a field, or the default if the page did not carry it."""
        return self.fields.get(name, default)

    def missing(self) -> tuple[str, ...]:
        """Return the required fields this block did not give up."""
        return tuple(name for name in REQUIRED_FIELDS if not self.fields.get(name))

    def complete(self) -> bool:
        """Return whether every required field came through."""
        return not self.missing()


@dataclass(frozen=True, slots=True)
class Extraction:
    """What one page gave up when a profile was applied to it."""

    reviews: tuple[RawReview, ...] = ()
    blocks_seen: int = 0
    dropped: tuple[str, ...] = ()
    next_page: str = ""
    notes: tuple[str, ...] = ()

    @property
    def yielded(self) -> int:
        """Return how many complete reviews came off the page."""
        return len(self.reviews)

    @property
    def empty(self) -> bool:
        """Return whether the page gave up nothing at all."""
        return not self.reviews


def _read_markup(rule: FieldRule, block: Element) -> str:
    """Read one field out of one review block.

    The block itself counts as a candidate. Channels hang the review id on the
    same element that wraps the review, and a reader that only looks at the
    descendants of that element never finds it.
    """
    selector = rule.compiled()
    found = block if selector.matches(block) else selector.first(block)
    if found is None:
        return ""
    if rule.source == "attribute":
        return found.get(rule.attribute).strip()
    return found.text(" ")


def _block_fields(profile: Profile, block: Element) -> dict[str, str]:
    fields: dict[str, str] = {}
    for rule in profile.markup_rules():
        value = _read_markup(rule, block)
        if value:
            fields[rule.name] = value
    return fields


def _structured_fields(profile: Profile, obj: Mapping[str, object]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for rule in profile.structured_rules():
        value = text_of(obj.get(rule.key))
        if value:
            fields[rule.name] = value
    return fields


IDENTIFIER_KEYS = ("identifier", "reviewId", "@id", "url")
"""Where a channel puts the review id inside a structured review object.

Matching needs an id whether or not the profile happens to read one, so these
are tried in order when the profile does not name one itself.
"""


def _object_id(profile: Profile, obj: Mapping[str, object]) -> str:
    """Return the channel review id on a structured object, if it carries one."""
    rule = profile.rule("channel_review_id")
    if rule is not None and rule.source == "structured":
        found = text_of(obj.get(rule.key))
        if found:
            return found
    for key in IDENTIFIER_KEYS:
        found = text_of(obj.get(key))
        if found:
            return found
    return ""


def _pair_up(
    profile: Profile,
    blocks: list[dict[str, str]],
    structured: Structured,
) -> tuple[list[dict[str, str]], list[str]]:
    """Return the block fields with structured values folded in, and what did not fit."""
    objects = structured.reviews()
    if not objects or not profile.structured_rules():
        return blocks, []
    parsed = [_structured_fields(profile, obj) for obj in objects]
    ids = [_object_id(profile, obj) for obj in objects]
    notes: list[str] = []
    by_id = {found: fields for found, fields in zip(ids, parsed, strict=True) if found}
    matched_ids: set[str] = set()
    for index, block in enumerate(blocks):
        found: dict[str, str] | None = None
        block_id = block.get("channel_review_id", "")
        if block_id and block_id in by_id:
            found = by_id[block_id]
            matched_ids.add(block_id)
        elif not by_id and len(parsed) == len(blocks):
            found = parsed[index]
        if found is None:
            continue
        for name, value in found.items():
            if profile.prefer_structured or not block.get(name):
                block[name] = value
    loose = len(parsed) - len(matched_ids)
    if by_id and loose:
        notes.append(f"{loose} structured reviews did not match a block on the page")
    elif not by_id and len(parsed) != len(blocks):
        notes.append(
            f"{len(parsed)} structured reviews against {len(blocks)} blocks, none were folded in"
        )
    return blocks, notes


def extract(profile: Profile, root: Element, page_url: str = "") -> Extraction:
    """Apply a profile to a parsed page and return what it gave up."""
    containers = profile.container_selector().select(root)
    structured = read(root)
    raw_blocks = [_block_fields(profile, block) for block in containers]
    folded, notes = _pair_up(profile, raw_blocks, structured)
    reviews: list[RawReview] = []
    dropped: list[str] = []
    for index, fields in enumerate(folded):
        candidate = RawReview(dict(fields), profile.key(), index)
        if candidate.complete():
            reviews.append(candidate)
            continue
        dropped.append(f"block {index} had no {' or '.join(candidate.missing())}")
    following = ""
    selector = profile.next_page_selector()
    if selector is not None:
        link = selector.first(root)
        if link is not None and link.get("href"):
            following = urljoin(page_url, link.get("href")) if page_url else link.get("href")
    return Extraction(
        tuple(reviews),
        len(containers),
        tuple(dropped),
        following,
        (*structured.problems(), *notes),
    )
