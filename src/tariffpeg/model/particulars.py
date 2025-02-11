"""The schedule of particulars: the claims an operator registers on a licence.

The vocabulary is fixed by the licensing order, not by whoever is typing. An
operator cannot invent a particular and the unit cannot grade one that is not
listed here, because the whole point of a contradiction is that it is a
contradiction of something the operator signed for.

Each particular has a kind, and the kind decides how a review assertion is
compared against it. A flag is contradicted by its opposite. A count is
contradicted by a number outside its tolerance. A distance is contradicted only
when the guest's figure is further out than the tolerance in the same
direction, because nobody complains that the sea was closer than advertised.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from tariffpeg.errors import Invalid


class ClaimKind(StrEnum):
    """How a particular is measured, which decides how it can be contradicted."""

    FLAG = "flag"
    COUNT = "count"
    DISTANCE_M = "distance_m"
    BAND = "band"


@dataclass(frozen=True, slots=True)
class ClaimSpec:
    """One entry in the licensing order's list of particulars."""

    key: str
    kind: ClaimKind
    label: str
    tolerance: int = 0
    upper_only: bool = False

    def validate(self, value: bool | int) -> bool | int:
        """Return the value if it is admissible for this particular.

        Booleans are rejected for numeric particulars on purpose. ``True`` is
        an integer in Python and a bed count of ``True`` has been typed in by a
        real person before.
        """
        if self.kind is ClaimKind.FLAG:
            if not isinstance(value, bool):
                raise Invalid(self.key, value, "this particular is a yes or no")
            return value
        if isinstance(value, bool) or not isinstance(value, int):
            raise Invalid(self.key, value, "this particular is a whole number")
        if value < 0:
            raise Invalid(self.key, value, "this particular cannot be negative")
        if self.kind is ClaimKind.BAND and not 1 <= value <= 5:
            raise Invalid(self.key, value, "a grading band runs from one to five keys")
        return value

    def render(self, value: bool | int) -> str:
        """Render the value the way the case file prints it."""
        if self.kind is ClaimKind.FLAG:
            return "yes" if value else "no"
        if self.kind is ClaimKind.DISTANCE_M:
            return f"{value} m"
        if self.kind is ClaimKind.BAND:
            return f"{value} keys"
        return str(value)


SPECS: tuple[ClaimSpec, ...] = (
    ClaimSpec("lift", ClaimKind.FLAG, "a passenger lift serves the guest floors"),
    ClaimSpec("step_free_entrance", ClaimKind.FLAG, "the main entrance is step free"),
    ClaimSpec("en_suite_all", ClaimKind.FLAG, "every let room is en suite"),
    ClaimSpec("breakfast_included", ClaimKind.FLAG, "breakfast is in the room rate"),
    ClaimSpec("parking_on_site", ClaimKind.FLAG, "parking is on the premises"),
    ClaimSpec("wifi_all_rooms", ClaimKind.FLAG, "wireless internet reaches every room"),
    ClaimSpec("pets_accepted", ClaimKind.FLAG, "dogs are accepted in let rooms"),
    ClaimSpec("late_arrival", ClaimKind.FLAG, "arrival after ten at night is staffed"),
    ClaimSpec("let_rooms", ClaimKind.COUNT, "rooms let to guests", tolerance=0),
    ClaimSpec("bed_spaces", ClaimKind.COUNT, "bed spaces across all let rooms", tolerance=2),
    ClaimSpec("parking_spaces", ClaimKind.COUNT, "marked parking spaces", tolerance=1),
    ClaimSpec("shore_distance", ClaimKind.DISTANCE_M, "walking metres to the shore", 150, True),
    ClaimSpec("station_distance", ClaimKind.DISTANCE_M, "walking metres to the station", 250, True),
    ClaimSpec("grading_band", ClaimKind.BAND, "the awarded grading band"),
)
"""The particulars, in the order the licensing order lists them."""

BY_KEY: dict[str, ClaimSpec] = {spec.key: spec for spec in SPECS}


def spec_for(key: str) -> ClaimSpec:
    """Return the specification for a particular, or refuse the key."""
    try:
        return BY_KEY[key]
    except KeyError:
        raise Invalid("claim_key", key, "the licensing order lists no such particular") from None


def parse_value(key: str, text: str) -> bool | int:
    """Read a particular's value the way it arrives from the CLI or a form."""
    spec = spec_for(key)
    cleaned = text.strip().lower()
    if spec.kind is ClaimKind.FLAG:
        if cleaned in ("yes", "y", "true", "1"):
            return True
        if cleaned in ("no", "n", "false", "0"):
            return False
        raise Invalid(key, text, "write yes or no")
    stripped = cleaned.removesuffix("m").strip() if spec.kind is ClaimKind.DISTANCE_M else cleaned
    stripped = stripped.removesuffix("keys").strip() if spec.kind is ClaimKind.BAND else stripped
    try:
        value = int(stripped)
    except ValueError:
        raise Invalid(key, text, "write a whole number") from None
    return spec.validate(value)
