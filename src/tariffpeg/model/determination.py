"""What the unit minuted about a licence, on the day it minuted it.

A decision is worked out from the evidence every time it is asked for, which is
the right way round while the evidence is still being gathered and the wrong way
round once a letter has gone out. The operator was told a thing on a day. That
day's reading has to survive a later harvest, a later rule pack and a later view
of the same reviews, so it gets written down.

What gets written down is the reading, not the working. The working is the case
file and it can be rebuilt from the captures whenever anybody asks. What cannot
be rebuilt is which of several possible readings the unit acted on.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from tariffpeg.clock import require_utc
from tariffpeg.errors import Invalid
from tariffpeg.model.outcome import SENDS_SOMEBODY_OUT, Disposition, heavier
from tariffpeg.model.period import StayMonth

HELD = "held"
"""What the ledger says when a minute did not move the disposition."""

ESCALATED = "escalated"
"""What the ledger says when a minute moved further up the order."""

STEPPED_BACK = "stepped back"
"""What the ledger says when a minute moved back down it."""


@dataclass(frozen=True, slots=True)
class Determination:
    """One minuted decision, as the ledger holds it."""

    licence_serial: int
    decided_at: StayMonth
    disposition: Disposition
    score: float
    access_score: float
    capped: bool
    pack_version: int
    minuted_at: dt.datetime
    officer: str

    def __post_init__(self) -> None:
        if self.licence_serial < 1:
            raise Invalid("licence_serial", self.licence_serial, "a serial counts from one")
        if not self.officer.strip():
            raise Invalid("officer", self.officer, "a minute carries the name of who took it")
        if self.pack_version < 1:
            raise Invalid("pack_version", self.pack_version, "rule pack versions start at one")
        if self.score < 0 or self.access_score < 0:
            raise Invalid("score", self.score, "a score does not go below zero")
        require_utc(self.minuted_at, "minuted_at")

    @property
    def key(self) -> tuple[int, int, int]:
        """Return what the ledger holds one minute under."""
        return self.licence_serial, self.decided_at.year, self.decided_at.month

    @property
    def sent_somebody_out(self) -> bool:
        """Return whether this minute put a visit in a diary."""
        return self.disposition in SENDS_SOMEBODY_OUT

    def line(self) -> str:
        """Return the minute as the ledger prints it."""
        held = ", capped by an incomplete sample" if self.capped else ""
        return (
            f"{self.decided_at}: {self.disposition} at {self.score:.2f}"
            f" under pack {self.pack_version}, minuted by {self.officer}{held}"
        )


def movement(before: Determination, after: Determination) -> str:
    """Return how the second minute moved against the first.

    A move is named from the disposition and not from the score. A score that
    climbed without crossing a band changed nothing the operator was told, and a
    ledger that reports it as a change teaches everybody to skim the ledger.
    """
    if before.licence_serial != after.licence_serial:
        raise Invalid(
            "licence_serial", after.licence_serial, "these two minutes are not the same case"
        )
    if before.disposition is after.disposition:
        return HELD
    if heavier(before.disposition, after.disposition) is after.disposition:
        return ESCALATED
    return STEPPED_BACK


def unexplained(before: Determination, after: Determination) -> bool:
    """Return whether a step back happened without the rule pack moving.

    Stepping back after a new pack is published is ordinary, because the rules
    changed. Stepping back under the same pack means evidence went away, which
    happens when a channel takes reviews down, and somebody should look at it.
    """
    return movement(before, after) == STEPPED_BACK and before.pack_version == after.pack_version
