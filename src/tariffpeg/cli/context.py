"""What every command is handed, and how a refusal becomes an exit code.

The exit codes matter because this runs from a scheduler overnight. A run that
stopped because a channel refused us has to be told apart from a run that
stopped because somebody typed a reference wrong, without anybody reading the
output.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import click

from tariffpeg.clock import Clock, SystemClock
from tariffpeg.errors import TariffpegError
from tariffpeg.report.rows import Column, as_csv, render
from tariffpeg.settings import DEFAULTS, Settings, load
from tariffpeg.store.db import Database

EXIT_CODES = {
    "error": 1,
    "invalid": 2,
    "not_found": 3,
    "already_exists": 4,
    "conflict": 5,
    "fetch_failed": 6,
    "refused": 7,
}
"""What each kind of refusal exits with."""


def exit_code_for(err: TariffpegError) -> int:
    """Return the exit code a refusal produces."""
    return EXIT_CODES.get(err.code, EXIT_CODES["error"])


@dataclass(slots=True)
class Context:
    """The state every command shares."""

    database: Path
    settings: Settings = DEFAULTS
    clock: Clock = field(default_factory=SystemClock)
    as_csv: bool = False
    _db: Database | None = None

    def store(self) -> Database:
        """Return the open store, opening it the first time it is asked for."""
        if self._db is None:
            self._db = Database(self.database)
        return self._db

    def close(self) -> None:
        """Close the store if it was ever opened."""
        if self._db is not None:
            self._db.close()
            self._db = None

    def emit(self, rows: Sequence[Mapping[str, object]], columns: Sequence[Column]) -> None:
        """Print rows the way the caller asked for them."""
        if self.as_csv:
            click.echo(as_csv(rows, columns), nl=False)
            return
        for line in render(rows, columns):
            click.echo(line)

    def say(self, *lines: str) -> None:
        """Print plain lines."""
        for line in lines:
            click.echo(line)


@contextmanager
def refusals() -> Iterator[None]:
    """Turn a refusal into a message and an exit code."""
    try:
        yield
    except TariffpegError as err:
        raise click.exceptions.Exit(exit_code_for(err)) from _shout(err)


def _shout(err: TariffpegError) -> TariffpegError:
    click.echo(f"{err.code}: {err}", err=True)
    return err


def settings_from(path: str | None) -> Settings:
    """Return the settings, from a file if one was named."""
    return DEFAULTS if path is None else load(path)
