"""Running the command line against a store in a temporary directory."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from tariffpeg.cli.main import main

Run = Callable[..., Result]


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    """Where the store the command line tests write to lives."""
    return tmp_path / "evidence.sqlite3"


@pytest.fixture
def run(store_path: Path) -> Run:
    """Run the command line against a fresh store."""
    runner = CliRunner()

    def invoke(*args: str, extra: Sequence[str] = ()) -> Result:
        return runner.invoke(main, ["--db", str(store_path), *extra, *args])

    return invoke


@pytest.fixture
def migrated(run: Run) -> Run:
    """Run the command line against a store that has been migrated."""
    run("db", "migrate")
    return run
