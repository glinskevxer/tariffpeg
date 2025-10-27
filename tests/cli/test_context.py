"""A run that stopped because a channel refused us reads differently from a typo."""

from __future__ import annotations

from pathlib import Path

from tariffpeg.cli.context import EXIT_CODES, Context, exit_code_for, settings_from
from tariffpeg.errors import AlreadyExists, Conflict, FetchFailed, Invalid, NotFound, Refused
from tariffpeg.settings import DEFAULTS
from tests.cli.conftest import Run


def test_every_kind_of_refusal_has_its_own_exit_code() -> None:
    codes = {
        exit_code_for(NotFound("licence", "x")),
        exit_code_for(AlreadyExists("channel", "x")),
        exit_code_for(Invalid("x", 1, "y")),
        exit_code_for(Conflict("x", "y")),
        exit_code_for(FetchFailed("https://x.test", "y")),
        exit_code_for(Refused("https://x.test", "y")),
    }
    assert len(codes) == 6
    assert 0 not in codes
    assert set(codes) <= set(EXIT_CODES.values())


def test_a_refusal_nobody_listed_exits_with_the_general_code() -> None:
    from tariffpeg.errors import TariffpegError

    assert exit_code_for(TariffpegError("something")) == EXIT_CODES["error"]


def test_the_store_is_not_opened_until_something_asks_for_it(tmp_path: Path) -> None:
    target = tmp_path / "evidence.sqlite3"
    ctx = Context(database=target)
    assert not target.exists()
    ctx.store()
    assert target.exists()
    ctx.close()


def test_the_same_store_comes_back_every_time_it_is_asked_for(tmp_path: Path) -> None:
    ctx = Context(database=tmp_path / "evidence.sqlite3")
    assert ctx.store() is ctx.store()
    ctx.close()


def test_closing_a_store_that_was_never_opened_is_harmless(tmp_path: Path) -> None:
    Context(database=tmp_path / "evidence.sqlite3").close()


def test_closing_twice_is_harmless(tmp_path: Path) -> None:
    ctx = Context(database=tmp_path / "evidence.sqlite3")
    ctx.store()
    ctx.close()
    ctx.close()


def test_the_settings_are_the_defaults_when_no_file_is_named() -> None:
    assert settings_from(None) == DEFAULTS


def test_a_named_settings_file_is_read(tmp_path: Path) -> None:
    target = tmp_path / "tariffpeg.toml"
    target.write_text("[tariffpeg]\ncrawl_delay_ms = 5000\n", encoding="utf-8")
    assert settings_from(str(target)).crawl_delay_ms == 5000


def test_rows_can_be_asked_for_as_comma_separated_text(migrated: Run) -> None:
    result = migrated("db", "migrations", extra=["--csv"])
    assert result.output.splitlines()[0] == "number,name,state"


def test_a_settings_file_that_is_not_there_is_reported(run: Run, tmp_path: Path) -> None:
    result = run("db", "status", extra=["--config", str(tmp_path / "nothing.toml")])
    assert result.exit_code != 0
    assert "no settings file" in result.output
