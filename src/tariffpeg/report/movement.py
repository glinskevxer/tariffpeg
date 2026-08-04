"""The ledger against the reading the evidence gives today.

Every minute in the ledger was taken on the evidence that was in the store that
week. A later harvest brings in reviews of stays that had already happened, a
new rule pack reads sentences the old one walked past, and a channel takes a
listing down and takes its reviews with it. Any of those can move a licence
without anybody deciding anything.

So the two readings are set against each other and the differences are sorted
into the ones that explain themselves and the ones that do not. A licence that
escalated since it was minuted is the reason this report exists: the operator
was told one thing, the evidence now says another, and nobody has written to
them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from tariffpeg.model.determination import ESCALATED, HELD, STEPPED_BACK, Determination
from tariffpeg.model.outcome import Disposition, heavier
from tariffpeg.report.rows import Column
from tariffpeg.triage.disposition import Decision

COLUMNS = (
    Column("licence", "licence", numeric=True),
    Column("minuted", "minuted"),
    Column("then", "was"),
    Column("now", "reads as"),
    Column("moved", "moved"),
    Column("pack", "same pack"),
)
"""The columns the reconciliation prints as."""

UNMINUTED = "not minuted"
"""What the report says about a licence the ledger has never held."""


@dataclass(frozen=True, slots=True)
class Movement:
    """One licence, as it was minuted and as it reads now."""

    licence_serial: int
    minuted: Determination | None
    now: Disposition
    now_pack: int

    @property
    def known(self) -> bool:
        """Return whether the ledger has anything about this licence at all."""
        return self.minuted is not None

    @property
    def moved(self) -> str:
        """Return which way the reading has gone since it was minuted."""
        if self.minuted is None:
            return UNMINUTED
        if self.minuted.disposition is self.now:
            return HELD
        if heavier(self.minuted.disposition, self.now) is self.now:
            return ESCALATED
        return STEPPED_BACK

    @property
    def same_pack(self) -> bool:
        """Return whether the two readings were taken under the same rule pack."""
        return self.minuted is not None and self.minuted.pack_version == self.now_pack

    @property
    def wants_a_letter(self) -> bool:
        """Return whether the operator was told something that no longer holds.

        Only an escalation asks for a letter. A licence that has stepped back
        since it was minuted is a licence the operator was told the worse of two
        things about, and telling them the better one can wait for the next
        minute.
        """
        return self.moved == ESCALATED

    @property
    def unexplained(self) -> bool:
        """Return whether the reading moved without the rule pack moving."""
        return self.moved in (ESCALATED, STEPPED_BACK) and self.same_pack

    def row(self) -> dict[str, object]:
        """Return the row this licence prints as."""
        return {
            "licence": self.licence_serial,
            "minuted": str(self.minuted.decided_at) if self.minuted else "never",
            "then": str(self.minuted.disposition) if self.minuted else "",
            "now": str(self.now),
            "moved": self.moved,
            "pack": self.same_pack,
        }


@dataclass(frozen=True, slots=True)
class Reconciliation:
    """The whole register, ledger against live reading."""

    movements: tuple[Movement, ...] = ()

    def rows(self) -> list[dict[str, object]]:
        """Return one row per licence."""
        return [item.row() for item in self.movements]

    def moved(self) -> tuple[Movement, ...]:
        """Return only the licences whose reading has changed."""
        return tuple(item for item in self.movements if item.moved in (ESCALATED, STEPPED_BACK))

    def wanting_a_letter(self) -> tuple[int, ...]:
        """Return the licences whose operator was told something that no longer holds."""
        return tuple(item.licence_serial for item in self.movements if item.wants_a_letter)

    def unminuted(self) -> tuple[int, ...]:
        """Return the licences the ledger has never held anything about."""
        return tuple(item.licence_serial for item in self.movements if not item.known)

    def settled(self) -> bool:
        """Return whether every minuted licence still reads the way it was minuted."""
        return not self.moved()


def reconcile(
    minutes: Mapping[int, Determination | None],
    decisions: Sequence[Decision],
    pack_version: int,
) -> Reconciliation:
    """Return the ledger set against the reading the evidence gives now.

    The decisions drive the report, not the ledger. A licence that was minuted
    and has since been surrendered has no live decision, and putting it in this
    report would send somebody chasing a licence that no longer exists.
    """
    return Reconciliation(
        tuple(
            sorted(
                (
                    Movement(
                        licence_serial=decision.licence_serial,
                        minuted=minutes.get(decision.licence_serial),
                        now=decision.disposition,
                        now_pack=pack_version,
                    )
                    for decision in decisions
                ),
                key=lambda item: item.licence_serial,
            )
        )
    )
