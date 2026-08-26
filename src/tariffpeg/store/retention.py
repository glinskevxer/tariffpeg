"""Dropping the page bodies nothing is relying on any more.

A store that keeps every page it ever read grows without limit, and most of
those pages are behind reviews that nothing has ever quoted. So bodies get
dropped. What is not dropped is anything a case file quotes, and the list of
those is passed in rather than worked out here, because the layer that knows
which quotations count is a long way above this one.

Two lists come in, not one. A page a live case file quotes is protected because
the case is still open. A page a minuted decision quoted is protected for good,
because that page is what the operator was written to on the strength of, and it
has to be producible whether or not the case still reads that way today.

Nothing is dropped without a plan being built first and looked at. That is not
politeness, it is the difference between a retention rule and an accident.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass

from tariffpeg.errors import Invalid
from tariffpeg.store.captures import CaptureStore
from tariffpeg.store.db import Database


@dataclass(frozen=True, slots=True)
class Prune:
    """What a retention run would drop, and what it would keep."""

    dropping: tuple[str, ...]
    bytes_freed: int
    kept_in_use: tuple[str, ...]
    kept_recent: tuple[str, ...]
    kept_minuted: tuple[str, ...] = ()

    @property
    def count(self) -> int:
        """Return how many bodies would go."""
        return len(self.dropping)

    def lines(self) -> tuple[str, ...]:
        """Return what the plan says, for somebody to read before it runs."""
        return (
            f"{self.count} page bodies would go, freeing {self.bytes_freed} bytes",
            f"{len(self.kept_in_use)} are quoted in a live case file and stay",
            f"{len(self.kept_minuted)} are behind a minuted decision and never go",
            f"{len(self.kept_recent)} are too recent to drop and stay",
        )


def plan(
    db: Database,
    before: dt.date,
    in_use: Iterable[str] = (),
    minuted: Iterable[str] = (),
) -> Prune:
    """Return what a retention run would do, without doing any of it."""
    cited = set(minuted)
    protected = set(in_use) - cited
    dropping: list[str] = []
    kept_in_use: list[str] = []
    kept_recent: list[str] = []
    kept_minuted: list[str] = []
    freed = 0
    rows = db.conn.execute(
        "SELECT c.digest AS digest, c.fetched_at AS fetched_at, length(b.body) AS size"
        " FROM capture c JOIN capture_body b ON b.digest = c.digest"
        " ORDER BY c.fetched_at, c.digest"
    ).fetchall()
    for row in rows:
        digest = str(row["digest"])
        if digest in cited:
            kept_minuted.append(digest)
            continue
        if digest in protected:
            kept_in_use.append(digest)
            continue
        if str(row["fetched_at"])[:10] >= before.isoformat():
            kept_recent.append(digest)
            continue
        dropping.append(digest)
        freed += int(row["size"] or 0)
    return Prune(
        tuple(dropping),
        freed,
        tuple(kept_in_use),
        tuple(kept_recent),
        tuple(kept_minuted),
    )


def run(db: Database, prune: Prune) -> int:
    """Drop the bodies a plan named, and return how many went.

    The plan is the only way in. A caller that wants to drop one body reaches
    for the capture store, and a caller that wants to drop many builds a plan
    and looks at it, because the second one is the one that gets typed at the
    end of a long day.
    """
    if not prune.dropping:
        return 0
    captures = CaptureStore(db)
    for digest in prune.dropping:
        if not captures.exists(digest):
            raise Invalid("digest", digest, "the plan names a capture that is not here any more")
    with db.transaction():
        for digest in prune.dropping:
            captures.forget_body(digest)
    return len(prune.dropping)
