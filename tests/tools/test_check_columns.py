"""A column with nothing under it prints as an empty stripe down the table."""

from __future__ import annotations

from tariffpeg.tools import check_columns
from tariffpeg.tools.walk import SourceFile
from tests.tools.conftest import Planter, make_source

DOC = chr(34) * 3
NL = chr(10)
HEAD = DOC + "x." + DOC + NL * 2 + "from tariffpeg.report.rows import Column" + NL * 2
COLUMNS = (
    "COLUMNS = ("
    + "\n"
    + '    Column("licence", "licence", numeric=True),'
    + "\n"
    + '    Column("channel", "channel"),'
    + "\n"
    + '    Column("pages", "pages", numeric=True),'
    + "\n"
    + ")"
    + "\n"
    + "\n"
    + "\n"
)
GOOD = (
    HEAD
    + COLUMNS
    + (
        "def row() -> dict[str, object]:"
        + "\n"
        + '    """Return a row."""'
        + "\n"
        + '    return {"licence": 1, "channel": "seaboard", "pages": 4}'
        + "\n"
    )
)
MISSING = (
    HEAD
    + COLUMNS
    + (
        "def row() -> dict[str, object]:"
        + "\n"
        + '    """Return a row."""'
        + "\n"
        + '    return {"licence": 1, "channel": "seaboard"}'
        + "\n"
    )
)
EXTRA = (
    HEAD
    + COLUMNS
    + (
        "def row() -> dict[str, object]:"
        + "\n"
        + '    """Return a row."""'
        + "\n"
        + '    return {"licence": 1, "channel": "seaboard", "pages": 4, "why": "short"}'
        + "\n"
    )
)
COMPUTED = (
    HEAD
    + COLUMNS
    + (
        "def row(key: str) -> dict[str, object]:"
        + "\n"
        + '    """Return a row."""'
        + "\n"
        + '    return {key: 1, "channel": "seaboard"}'
        + "\n"
    )
)
UNRELATED = HEAD + COLUMNS + ('SPEND = {"seaboard": 3, "quayside": 0}' + "\n")
TWO_TABLES = (
    HEAD
    + COLUMNS
    + (
        "OTHER = ("
        + "\n"
        + '    Column("licence", "licence", numeric=True),'
        + "\n"
        + '    Column("channel", "channel"),'
        + "\n"
        + '    Column("inspector", "inspector"),'
        + "\n"
        + ")"
        + "\n"
        + "\n"
        + "\n"
        + "def row() -> dict[str, object]:"
        + "\n"
        + '    """Return a row."""'
        + "\n"
        + '    return {"licence": 1, "channel": "seaboard"}'
        + "\n"
    )
)


def one(text: str) -> list[SourceFile]:
    return [make_source("tariffpeg/cli/x.py", text)]


def test_every_row_in_the_real_tree_matches_its_columns() -> None:
    assert check_columns.problems() == []


def test_a_row_that_matches_its_columns_reads_clean(plant: Planter) -> None:
    plant(check_columns, "package_files", one(GOOD))
    assert check_columns.problems() == []


def test_a_column_with_nothing_under_it_is_reported(plant: Planter) -> None:
    plant(check_columns, "package_files", one(MISSING))
    found = check_columns.problems()
    assert len(found) == 1
    assert "it has no pages for" in found[0]


def test_a_key_no_column_prints_is_reported(plant: Planter) -> None:
    plant(check_columns, "package_files", one(EXTRA))
    found = check_columns.problems()
    assert len(found) == 1
    assert "a row carries why" in found[0]


def test_a_row_with_a_computed_key_is_left_alone(plant: Planter) -> None:
    plant(check_columns, "package_files", one(COMPUTED))
    assert check_columns.problems() == []


def test_a_dictionary_that_is_not_a_row_is_left_alone(plant: Planter) -> None:
    plant(check_columns, "package_files", one(UNRELATED))
    assert check_columns.problems() == []


def test_a_row_that_two_tables_fit_equally_well_is_left_alone(plant: Planter) -> None:
    plant(check_columns, "package_files", one(TWO_TABLES))
    assert check_columns.problems() == []


def test_a_file_with_no_columns_in_it_is_left_alone(plant: Planter) -> None:
    text = DOC + "x." + DOC + "\n" + "\n" + 'ROW = {"licence": 1, "channel": "a"}' + "\n"
    plant(check_columns, "package_files", one(text))
    assert check_columns.problems() == []


def test_the_column_keys_are_read_off_the_calls() -> None:
    found = check_columns.column_sets(make_source("tariffpeg/cli/x.py", GOOD))
    assert frozenset({"licence", "channel", "pages"}) in [keys for _, keys in found]
