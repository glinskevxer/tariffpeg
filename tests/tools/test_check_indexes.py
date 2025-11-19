"""The difference only shows up in front of somebody who is waiting."""

from __future__ import annotations

import pytest

from tariffpeg.store.migrations import Migration
from tariffpeg.tools import check_indexes

PARENT = """
CREATE TABLE licence (
    serial INTEGER PRIMARY KEY,
    name   TEXT NOT NULL
)
"""
CHILD = """
CREATE TABLE review (
    review_key     TEXT PRIMARY KEY,
    licence_serial INTEGER NOT NULL REFERENCES licence(serial) ON DELETE CASCADE,
    body           TEXT NOT NULL
)
"""
COMPOUND = """
CREATE TABLE listing (
    licence_serial INTEGER NOT NULL REFERENCES licence(serial),
    channel        TEXT NOT NULL REFERENCES channel(slug),
    path           TEXT NOT NULL,
    PRIMARY KEY (licence_serial, channel)
)
"""


def plant_schema(monkeypatch: pytest.MonkeyPatch, *statements: str) -> None:
    monkeypatch.setattr(check_indexes, "MIGRATIONS", (Migration(1, "x", statements),))


def test_the_real_schema_indexes_everything_that_points_somewhere() -> None:
    assert check_indexes.problems() == []


def test_a_pointing_column_with_an_index_reads_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    plant_schema(
        monkeypatch, PARENT, CHILD, "CREATE INDEX review_licence ON review(licence_serial)"
    )
    assert check_indexes.problems() == []


def test_a_pointing_column_with_no_index_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    plant_schema(monkeypatch, PARENT, CHILD)
    found = check_indexes.problems()
    assert found == ["review.licence_serial points at another table with no index on it"]


def test_an_index_that_starts_with_the_column_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    plant_schema(
        monkeypatch, PARENT, CHILD, "CREATE INDEX review_x ON review(licence_serial, body)"
    )
    assert check_indexes.problems() == []


def test_an_index_that_only_mentions_the_column_second_does_not_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plant_schema(
        monkeypatch, PARENT, CHILD, "CREATE INDEX review_x ON review(body, licence_serial)"
    )
    assert check_indexes.problems() == [
        "review.licence_serial points at another table with no index on it"
    ]


def test_a_unique_index_counts_the_same_as_any_other(monkeypatch: pytest.MonkeyPatch) -> None:
    plant_schema(
        monkeypatch, PARENT, CHILD, "CREATE UNIQUE INDEX review_x ON review(licence_serial)"
    )
    assert check_indexes.problems() == []


def test_the_leading_column_of_a_compound_key_needs_no_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plant_schema(monkeypatch, COMPOUND, "CREATE INDEX listing_channel ON listing(channel)")
    assert check_indexes.problems() == []


def test_the_second_column_of_a_compound_key_still_needs_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plant_schema(monkeypatch, COMPOUND)
    found = check_indexes.problems()
    assert found == ["listing.channel points at another table with no index on it"]


def test_a_table_that_points_nowhere_is_left_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    plant_schema(monkeypatch, PARENT)
    assert check_indexes.problems() == []


def test_the_schema_reader_finds_the_pointing_and_indexed_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plant_schema(
        monkeypatch, PARENT, CHILD, "CREATE INDEX review_licence ON review(licence_serial)"
    )
    pointing, indexed, leading = check_indexes.read_schema()
    assert pointing == {"review": ["licence_serial"]}
    assert indexed == {"review": ["licence_serial"]}
    assert leading == {"licence": "serial", "review": "review_key"}


def test_the_check_exits_nothing_on_a_clean_schema() -> None:
    assert check_indexes.main() == 0


def test_the_check_exits_one_when_it_finds_something(monkeypatch: pytest.MonkeyPatch) -> None:
    plant_schema(monkeypatch, PARENT, CHILD)
    assert check_indexes.main() == 1
