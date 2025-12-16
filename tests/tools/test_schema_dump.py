"""The schema document is written out of the migrations that build it."""

from __future__ import annotations

from tariffpeg.store.migrations import MIGRATIONS
from tariffpeg.tools import schema_dump


def test_the_document_on_disk_is_what_the_code_would_write() -> None:
    assert schema_dump.main() == 0


def test_the_document_is_up_to_date(monkeypatch: object) -> None:
    from tariffpeg.tools.document import stale

    assert stale(schema_dump.DOCUMENT, schema_dump.text()) == ""


def test_every_migration_has_a_heading_of_its_own() -> None:
    text = schema_dump.text()
    for migration in MIGRATIONS:
        assert f"## {migration.number:03d} {migration.name}" in text


def test_every_migration_carries_the_digest_that_is_locked() -> None:
    text = schema_dump.text()
    for migration in MIGRATIONS:
        assert migration.digest in text


def test_every_table_the_migrations_make_has_a_heading() -> None:
    text = schema_dump.text()
    for table in ("licence", "channel", "capture", "review", "listing", "remediation"):
        assert f"### `{table}`" in text


def test_the_columns_of_a_table_are_listed_with_their_types() -> None:
    text = schema_dump.text()
    assert "| `trading_name` | TEXT | NOT NULL |" in text
    assert "| `serial` | INTEGER | PRIMARY KEY |" in text


def test_a_compound_primary_key_is_not_listed_as_a_column() -> None:
    assert "| `PRIMARY` |" not in schema_dump.text()


def test_the_indexes_are_listed_with_what_they_cover() -> None:
    text = schema_dump.text()
    assert "### indexes" in text
    assert "`licence_locality`" in text
    assert "`listing_property`" in text


def test_a_unique_index_is_marked_as_one() -> None:
    lines = [line for line in schema_dump.text().splitlines() if "listing_property" in line]
    assert lines[0].endswith("| yes |")


def test_an_ordinary_index_is_not_marked_unique() -> None:
    lines = [line for line in schema_dump.text().splitlines() if "licence_locality" in line]
    assert lines[0].endswith("| no |")


def test_the_document_says_what_wrote_it() -> None:
    assert "Written by schema_dump" in schema_dump.text()
