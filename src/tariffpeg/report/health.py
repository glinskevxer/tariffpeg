"""One reading of whether the unit is keeping up, for a machine to act on.

Every part of this is available somewhere else. The store verifies itself, the
letters know when they are late, the sample knows how short it is and the ledger
knows what it has not been told. What was missing was a single answer, because
the overnight job needs one and nobody reads six.

A check is either a fault or a warning. A fault means the evidence cannot be
relied on and the run should stop: the file does not verify, or its schema is
not the one this build writes. A warning means the unit is behind, which is
ordinary and worth printing. The distinction is the whole point of the module.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from tariffpeg.report.rows import Column

COLUMNS = (
    Column("check", "check"),
    Column("state", "state"),
    Column("detail", "what it found"),
)
"""The columns a health reading prints as."""

FAULT = "fault"
"""The store cannot be relied on and the run should stop."""

WARNING = "warning"
"""The unit is behind, which somebody should see."""

CLEAR = "clear"
"""Nothing to say."""


@dataclass(frozen=True, slots=True)
class Reading:
    """What one check found."""

    name: str
    state: str
    detail: str = ""

    @property
    def bad(self) -> bool:
        """Return whether this reading is one somebody has to act on."""
        return self.state in (FAULT, WARNING)

    def row(self) -> dict[str, object]:
        """Return the row this reading prints as."""
        return {"check": self.name, "state": self.state, "detail": self.detail or "nothing to say"}


@dataclass(frozen=True, slots=True)
class Health:
    """Every check, in the order they were run."""

    readings: tuple[Reading, ...] = ()

    def rows(self) -> list[dict[str, object]]:
        """Return one row per check."""
        return [reading.row() for reading in self.readings]

    def faults(self) -> tuple[Reading, ...]:
        """Return the checks that say the evidence cannot be relied on."""
        return tuple(reading for reading in self.readings if reading.state == FAULT)

    def warnings(self) -> tuple[Reading, ...]:
        """Return the checks that say the unit is behind."""
        return tuple(reading for reading in self.readings if reading.state == WARNING)

    @property
    def sound(self) -> bool:
        """Return whether nothing at all needs acting on."""
        return not self.faults() and not self.warnings()

    def exit_code(self) -> int:
        """Return what the command exits with.

        A fault is worse than a warning and a warning is worse than nothing, and
        the overnight job wants to tell the three apart without reading the
        output, so they get three different numbers.
        """
        if self.faults():
            return 2
        if self.warnings():
            return 1
        return 0

    def summary(self) -> str:
        """Return the one line a log carries."""
        if self.sound:
            return f"{len(self.readings)} checks, nothing to act on"
        return (
            f"{len(self.readings)} checks, {len(self.faults())} faults"
            f" and {len(self.warnings())} warnings"
        )


def fault(name: str, detail: str) -> Reading:
    """Return a reading that says the evidence cannot be relied on."""
    return Reading(name, FAULT, detail)


def warning(name: str, detail: str) -> Reading:
    """Return a reading that says the unit is behind."""
    return Reading(name, WARNING, detail)


def clear(name: str, detail: str = "") -> Reading:
    """Return a reading with nothing to say."""
    return Reading(name, CLEAR, detail)


def worst_of(readings: Sequence[Reading]) -> str:
    """Return the worst state in a set of readings."""
    states = {reading.state for reading in readings}
    if FAULT in states:
        return FAULT
    if WARNING in states:
        return WARNING
    return CLEAR
