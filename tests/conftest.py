"""Fixtures every layer of the suite leans on.

The store fixture closes the connection on the way out. Warnings are errors in
this suite, and a connection that falls out of scope unclosed is a warning on
some interpreters and silence on others, which is the worst of both.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from pathlib import Path

import pytest

from tariffpeg.clock import FixedClock
from tariffpeg.store.db import Database
from tariffpeg.store.migrations import migrate

STARTED = dt.datetime(2025, 6, 12, 9, 0, tzinfo=dt.UTC)
"""Where every fixed clock in the suite starts, unless a test moves it."""


@pytest.fixture
def clock() -> FixedClock:
    """A clock parked in the middle of a trading season."""
    return FixedClock(STARTED)


@pytest.fixture
def db(clock: FixedClock) -> Iterator[Database]:
    """A migrated store in memory, closed when the test finishes."""
    store = Database()
    migrate(store, clock)
    try:
        yield store
    finally:
        store.close()


@pytest.fixture
def file_db(tmp_path: Path, clock: FixedClock) -> Iterator[Database]:
    """A migrated store on disk, for the tests that care that it is a file."""
    store = Database(tmp_path / "evidence.sqlite3")
    migrate(store, clock)
    try:
        yield store
    finally:
        store.close()
