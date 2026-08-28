"""An operator disputing a case file gets told what read their reviews."""

from __future__ import annotations

from tariffpeg import __version__
from tariffpeg.claims.pack import PACK, published_versions
from tariffpeg.cli.about import COLUMNS, facts
from tariffpeg.model.particulars import SPECS
from tariffpeg.store.migrations import MIGRATIONS
from tests.cli.conftest import Run


def value_of(name: str) -> object:
    return [row["value"] for row in facts() if row["fact"] == name][0]


def test_every_fact_prints_under_a_column() -> None:
    keys = {column.key for column in COLUMNS}
    for row in facts():
        assert set(row) == keys


def test_the_build_names_the_version_it_was_cut_at() -> None:
    assert value_of("version") == __version__


def test_the_build_names_the_pack_that_read_the_reviews() -> None:
    assert value_of("rule pack in force") == PACK.version
    assert value_of("rules") == len(PACK.rules)


def test_the_build_names_every_pack_it_can_still_read() -> None:
    assert value_of("rule packs readable") == ", ".join(
        str(number) for number in published_versions()
    )


def test_the_build_names_the_schema_it_writes() -> None:
    assert value_of("schema version") == len(MIGRATIONS)
    assert value_of("particulars") == len(SPECS)


def test_the_command_prints_the_facts(run: Run) -> None:
    result = run("about")
    assert result.exit_code == 0
    assert __version__ in result.output
    assert "schema version" in result.output


def test_the_command_needs_no_store_to_answer(run: Run) -> None:
    result = run("about")
    assert result.exit_code == 0
    assert "rule pack in force" in result.output
