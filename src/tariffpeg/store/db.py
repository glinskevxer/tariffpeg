"""The book of record is a single SQLite file, opened the same way everywhere.

An evidence bundle gets copied onto a memory stick and handed to a hearing, so
the store has to be one file with nothing beside it. Everything that opens it
goes through :func:`connect` so that the pragmas are not something one caller
remembers and another forgets.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType

from tariffpeg.errors import Conflict

MEMORY = ":memory:"
"""The path that opens a store which is thrown away when it is closed."""


def connect(path: str | Path) -> sqlite3.Connection:
    """Open the store with the pragmas every caller depends on.

    Foreign keys are off by default in SQLite and the whole evidence chain is
    held together by them, so they go on here rather than in each caller.
    """
    target = str(path)
    conn = sqlite3.connect(target, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    if target != MEMORY:
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


class Database:
    """An open store, with the transaction helper the writers use.

    Closing is not optional. The tests run with warnings promoted to errors and
    a connection that falls out of scope unclosed is reported as one.
    """

    def __init__(self, path: str | Path = MEMORY) -> None:
        self.path = str(path)
        self.conn = connect(path)
        self._depth = 0

    def __enter__(self) -> Database:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying connection. Calling twice is harmless."""
        self.conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Run a block inside one transaction, nesting as a no-op.

        Nested calls join the outermost transaction rather than opening a
        savepoint. A writer that half succeeds is worse than one that fails, and
        no caller here wants partial rollback.
        """
        if self._depth:
            self._depth += 1
            try:
                yield self.conn
            finally:
                self._depth -= 1
            return
        self.conn.execute("BEGIN IMMEDIATE")
        self._depth = 1
        try:
            yield self.conn
        except BaseException:
            self._depth = 0
            self.conn.execute("ROLLBACK")
            raise
        self._depth = 0
        self.conn.execute("COMMIT")

    def in_transaction(self) -> bool:
        """Return whether a transaction opened by :meth:`transaction` is running."""
        return self._depth > 0

    def require_transaction(self, what: str) -> None:
        """Refuse a write that was not wrapped in a transaction."""
        if not self._depth:
            raise Conflict(what, "this write has to run inside a transaction")

    def table_names(self) -> tuple[str, ...]:
        """Return the tables in the store, excluding SQLite's own."""
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return tuple(str(row["name"]) for row in rows)

    def index_names(self) -> tuple[str, ...]:
        """Return the indexes the migrations created, excluding SQLite's own."""
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'"
            " AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return tuple(str(row["name"]) for row in rows)

    def integrity_problems(self) -> tuple[str, ...]:
        """Return what SQLite says is wrong with the file, if anything."""
        problems: list[str] = []
        for row in self.conn.execute("PRAGMA integrity_check"):
            message = str(row[0])
            if message != "ok":
                problems.append(message)
        for row in self.conn.execute("PRAGMA foreign_key_check"):
            problems.append(f"orphan row in {row[0]} pointing at {row[2]}")
        return tuple(problems)
