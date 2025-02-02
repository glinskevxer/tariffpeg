"""Identifiers the unit prints on paper and reads back off a form.

A licence reference is written on the plaque in the hall and typed back in by
whoever answers the phone, so it carries a check character. Everything else is
either a slug the unit chooses or a digest the fetcher computes.
"""

from __future__ import annotations

import hashlib
import re

LICENCE_DIGITS = 6
"""How many digits sit between the prefix and the check character."""

_CHECK_ALPHABET = "BCDFGHJKLMNPRSTVWXZ"
"""Nineteen consonants. A licence reference read out over the phone never
contains a letter that sounds like another letter, and never spells a word.
The count is prime on purpose, which is what makes the weighting below catch
every single wrong digit and every swap of two neighbours."""

_LICENCE_RE = re.compile(r"^L-(\d{6})-([BCDFGHJKLMNPRSTVWXZ])$")
_SLUG_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


def licence_check_character(serial: int) -> str:
    """Return the check character for a licence serial number.

    The weighting runs right to left over the printed digits, and the alphabet
    has a prime number of letters in it. Together that means the two mistakes
    people actually make, a single wrong digit and a swap of two neighbours,
    always change the character rather than usually changing it.
    """
    if serial < 0 or serial >= 10**LICENCE_DIGITS:
        raise ValueError(f"a licence serial has {LICENCE_DIGITS} digits, got {serial}")
    digits = f"{serial:0{LICENCE_DIGITS}d}"
    total = 0
    for position, digit in enumerate(reversed(digits)):
        total += (position + 2) * int(digit)
    return _CHECK_ALPHABET[total % len(_CHECK_ALPHABET)]


def format_licence_ref(serial: int) -> str:
    """Render a licence serial as the reference printed on the plaque."""
    return f"L-{serial:0{LICENCE_DIGITS}d}-{licence_check_character(serial)}"


def parse_licence_ref(ref: str) -> int:
    """Return the serial behind a licence reference, checking the character.

    Whitespace and case are forgiven because the reference arrives typed by
    hand. A wrong check character is not forgiven.
    """
    cleaned = ref.strip().upper().replace(" ", "")
    match = _LICENCE_RE.match(cleaned)
    if match is None:
        raise ValueError(f"{ref!r} is not shaped like a licence reference")
    serial = int(match.group(1))
    if match.group(2) != licence_check_character(serial):
        raise ValueError(f"{ref!r} has the wrong check character")
    return serial


def is_licence_ref(ref: str) -> bool:
    """Return whether the string parses as a licence reference."""
    try:
        parse_licence_ref(ref)
    except ValueError:
        return False
    return True


def normalise_slug(value: str) -> str:
    """Return the slug form of a name the unit typed in.

    Slugs name channels and room classes. They are lowercase, hyphen separated
    and never start with a digit, because they end up as column headings and as
    directory names in an evidence bundle.
    """
    lowered = value.strip().lower()
    collapsed = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    if not collapsed:
        raise ValueError(f"{value!r} has nothing in it that can become a slug")
    if collapsed[0].isdigit():
        raise ValueError(f"{value!r} would become a slug starting with a digit")
    return collapsed


def is_slug(value: str) -> bool:
    """Return whether the string is already in slug form."""
    return bool(_SLUG_RE.match(value))


def capture_digest(body: bytes) -> str:
    """Return the content digest recorded against a fetched response.

    The prefix stays in the string. The unit has changed hash once already and
    an evidence bundle from before that change still has to verify.
    """
    return "sha256:" + hashlib.sha256(body).hexdigest()


def review_key(channel: str, channel_review_id: str) -> str:
    """Return the store key for a review as that channel numbers it.

    Channels reuse short numbers, so the channel slug is part of the key rather
    than a column beside it.
    """
    if not is_slug(channel):
        raise ValueError(f"{channel!r} is not a channel slug")
    trimmed = channel_review_id.strip()
    if not trimmed:
        raise ValueError("a channel review id cannot be blank")
    return f"{channel}:{trimmed}"
