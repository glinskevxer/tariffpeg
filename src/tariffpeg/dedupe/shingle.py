"""Fingerprinting a review body so two copies of it can be recognised.

Aggregator channels reproduce reviews written elsewhere. They do not reproduce
them exactly: the body gets trimmed to a length, the punctuation gets tidied,
and sometimes a leading pleasantry is dropped. So the comparison is over runs of
words rather than over the string.

The permutations are fixed constants and the hash is keyed by them. Nothing here
draws a random number. A signature computed today has to equal the one computed
against the same body in three years, on a different machine, for the evidence
bundle to still hold together.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from tariffpeg.errors import Invalid

SHINGLE_WORDS = 5
"""How many words make one run. Shorter than this and ordinary sentences about
breakfast collide with each other."""

SIGNATURE_SLOTS = 64
"""How many permutations the signature keeps. Sixty four puts the error on an
estimated overlap at a few points, which is well inside the margin the
syndication rules use."""

_KEEP = re.compile(r"[^a-z0-9\s]+")
_MAXIMUM = (1 << 64) - 1


def flatten_text(text: str) -> str:
    """Return the text reduced to lowercase words with the punctuation gone."""
    lowered = text.lower().replace("-", " ")
    stripped = _KEEP.sub(" ", lowered)
    return " ".join(stripped.split())


def shingles(text: str, size: int = SHINGLE_WORDS) -> frozenset[str]:
    """Return the runs of words in a body.

    A body shorter than one run is one shingle of itself, so two short reviews
    that say the same three words still match each other.
    """
    if size < 1:
        raise Invalid("size", size, "a run is one word or more")
    words = flatten_text(text).split()
    if not words:
        return frozenset()
    if len(words) <= size:
        return frozenset({" ".join(words)})
    return frozenset(" ".join(words[at : at + size]) for at in range(len(words) - size + 1))


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    """Return the exact overlap between two sets of runs."""
    if not left and not right:
        return 1.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _slot_hash(run: str, slot: int) -> int:
    digest = hashlib.blake2b(
        run.encode("utf-8"),
        digest_size=8,
        person=slot.to_bytes(2, "big") + b"tariffpg",
    )
    return int.from_bytes(digest.digest(), "big")


@dataclass(frozen=True, slots=True)
class Signature:
    """A fixed width fingerprint of a review body."""

    slots: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.slots) != SIGNATURE_SLOTS:
            raise Invalid("slots", len(self.slots), f"a signature has {SIGNATURE_SLOTS} slots")

    @classmethod
    def of(cls, text: str, size: int = SHINGLE_WORDS) -> Signature:
        """Return the signature of a review body."""
        runs = shingles(text, size)
        if not runs:
            return cls((_MAXIMUM,) * SIGNATURE_SLOTS)
        slots = tuple(min(_slot_hash(run, slot) for run in runs) for slot in range(SIGNATURE_SLOTS))
        return cls(slots)

    @property
    def empty(self) -> bool:
        """Return whether this signature came from a body with no words in it."""
        return all(slot == _MAXIMUM for slot in self.slots)

    def similarity(self, other: Signature) -> float:
        """Return the estimated overlap with another signature."""
        if self.empty and other.empty:
            return 1.0
        if self.empty or other.empty:
            return 0.0
        agree = sum(
            1 for mine, theirs in zip(self.slots, other.slots, strict=True) if mine == theirs
        )
        return agree / SIGNATURE_SLOTS

    def encode(self) -> str:
        """Return the signature as the string the store holds."""
        return ",".join(f"{slot:016x}" for slot in self.slots)

    @classmethod
    def decode(cls, text: str) -> Signature:
        """Read a signature back off a row."""
        parts = text.split(",")
        if len(parts) != SIGNATURE_SLOTS:
            raise Invalid("signature", len(parts), f"a signature has {SIGNATURE_SLOTS} slots")
        try:
            return cls(tuple(int(part, 16) for part in parts))
        except ValueError:
            raise Invalid("signature", text[:32], "a signature is written in hexadecimal") from None
