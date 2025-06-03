"""Taking the personal data out before anything is written down.

A guest review is somebody writing about their holiday under their own name.
The unit has no business keeping the name, the phone number they left for the
owner, or the booking reference they quoted in a complaint. What it needs is
what they said about the lift.

Redaction happens on the way in and it does not come back. The digest of the
original capture is kept so the page can be fetched again under a warrant, but
the store never holds the name in the first place.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
LINK = re.compile(r"\b(?:https?://|www\.)\S+", re.I)
TELEPHONE = re.compile(r"(?<![\w.])\+?[\d][\d\s().-]{7,}\d(?![\w.])")
REFERENCE = re.compile(r"\b(?=[A-Z0-9-]{6,})(?=[A-Z-]*\d)[A-Z0-9-]{6,}\b")
DIGITS = re.compile(r"\d")

MARKERS = {
    "email": "[email removed]",
    "link": "[link removed]",
    "telephone": "[telephone removed]",
    "reference": "[booking reference removed]",
    "name": "[name removed]",
}
"""What replaces each kind of personal data. These strings end up in quotations
in a case file, so they read as sentences rather than as codes."""

MINIMUM_TELEPHONE_DIGITS = 9
"""Below this a run of digits is a room number or a price, not a telephone."""


@dataclass(frozen=True, slots=True)
class Redacted:
    """A piece of text with the personal data taken out of it."""

    text: str
    removed: tuple[tuple[str, int], ...] = ()

    @property
    def changed(self) -> bool:
        """Return whether anything had to be taken out."""
        return bool(self.removed)

    def count(self, kind: str) -> int:
        """Return how many of one kind were taken out."""
        for name, number in self.removed:
            if name == kind:
                return number
        return 0

    def summary(self) -> str:
        """Return one line naming what was taken out, for the harvest log."""
        if not self.removed:
            return "nothing removed"
        parts = [f"{number} {kind}" for kind, number in self.removed]
        return ", ".join(parts) + " removed"


def _telephone_is_long_enough(match: re.Match[str]) -> bool:
    return len(DIGITS.findall(match.group(0))) >= MINIMUM_TELEPHONE_DIGITS


def redact(text: str, reviewer_name: str = "") -> Redacted:
    """Return the text with every kind of personal data replaced.

    Order matters. Links go first because a link can carry an address inside
    it, and the reviewer name goes last because by then there is nothing left
    that could contain it by accident.
    """
    counts: dict[str, int] = {}
    working = text

    def swap(pattern: re.Pattern[str], kind: str, guard: object = None) -> None:
        nonlocal working
        removed = 0

        def replace(match: re.Match[str]) -> str:
            nonlocal removed
            if guard is not None and not guard(match):  # type: ignore[operator]
                return match.group(0)
            removed += 1
            return MARKERS[kind]

        working = pattern.sub(replace, working)
        if removed:
            counts[kind] = counts.get(kind, 0) + removed

    swap(LINK, "link")
    swap(EMAIL, "email")
    swap(TELEPHONE, "telephone", _telephone_is_long_enough)
    swap(REFERENCE, "reference")
    if reviewer_name.strip():
        pattern = re.compile(re.escape(reviewer_name.strip()), re.I)
        swap(pattern, "name")
    order = ("link", "email", "telephone", "reference", "name")
    return Redacted(working, tuple((kind, counts[kind]) for kind in order if kind in counts))


def redact_name(name: str) -> str:
    """Return a display name reduced to initials.

    The unit keeps enough to tell two reviews on one page apart and nothing
    more. A name that is already initials comes back unchanged.
    """
    parts = [part for part in re.split(r"[\s.]+", name.strip()) if part]
    if not parts:
        return ""
    return " ".join(f"{part[0].upper()}." for part in parts)


def is_clean(text: str) -> bool:
    """Return whether the text still carries anything that has to come out."""
    if EMAIL.search(text) or LINK.search(text) or REFERENCE.search(text):
        return False
    return not any(_telephone_is_long_enough(match) for match in TELEPHONE.finditer(text))
