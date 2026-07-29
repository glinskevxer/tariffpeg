"""What can happen to a licence, and which of those is the more serious.

This is four words and an order, and it sits in the model layer rather than
beside the arithmetic that picks between them because two other things need it
and neither of them is doing arithmetic. The ledger writes a disposition down
and reads it back years later. The scheduler asks whether one sends anybody out.

Keeping the order here also keeps it in one place. A second copy of "urgent
beats re-inspection" written somewhere else is the copy that will be wrong.
"""

from __future__ import annotations

from enum import StrEnum

from tariffpeg.errors import Invalid


class Disposition(StrEnum):
    """What happens to a licence, in order of seriousness."""

    NO_ACTION = "no action"
    DESK_ENQUIRY = "desk enquiry"
    REINSPECTION = "re-inspection"
    URGENT = "urgent re-inspection"


ORDER = (
    Disposition.NO_ACTION,
    Disposition.DESK_ENQUIRY,
    Disposition.REINSPECTION,
    Disposition.URGENT,
)
"""The dispositions from lightest to heaviest."""

SENDS_SOMEBODY_OUT = frozenset({Disposition.REINSPECTION, Disposition.URGENT})
"""The dispositions that put a visit in an inspector's diary."""


def heavier(one: Disposition, two: Disposition) -> Disposition:
    """Return whichever of two dispositions is the more serious."""
    return one if ORDER.index(one) >= ORDER.index(two) else two


def rank(disposition: Disposition) -> int:
    """Return where a disposition sits in the order, counting from nought."""
    return ORDER.index(disposition)


def parse_disposition(written: str) -> Disposition:
    """Return the disposition a stored string names, or refuse.

    The ledger holds these as text and a file written by a version that has
    since renamed one of them has to fail loudly rather than read back as no
    action, which is the value that looks like nothing went wrong.
    """
    for disposition in ORDER:
        if disposition.value == written:
            return disposition
    raise Invalid("disposition", written, "this is not a disposition the order carries")
