"""A test that has passed a thousand times fails once on somebody machine."""

from __future__ import annotations

from tariffpeg.tools import check_flake
from tariffpeg.tools.walk import SourceFile
from tests.tools.conftest import Planter, make_source

ORDERED = '''"""x."""


def all_of(conn: object) -> list[object]:
    """Read the rows."""
    return conn.execute("SELECT a FROM thing ORDER BY a").fetchall()
'''
UNORDERED = '''"""x."""


def all_of(conn: object) -> list[object]:
    """Read the rows."""
    return conn.execute("SELECT a FROM thing").fetchall()
'''
ONE = '''"""x."""


def one_of(conn: object) -> object:
    """Read one row."""
    return conn.execute("SELECT 1 FROM thing WHERE a = ?", (1,)).fetchone()
'''
COUNTED = '''"""x."""


def how_many(conn: object) -> object:
    """Count the rows."""
    return conn.execute("SELECT count(*) FROM thing").fetchall()
'''


FORMATTED = '''"""x."""

COLUMNS = "a, b"


def all_of(conn: object) -> list[object]:
    """Read the rows."""
    return conn.execute(f"SELECT {COLUMNS} FROM thing").fetchall()
'''
JOINED = '''"""x."""


def all_of(conn: object) -> list[object]:
    """Read the rows."""
    return conn.execute("SELECT a" + " FROM thing").fetchall()
'''
NOT_A_QUERY = '''"""x."""


def go(conn: object) -> None:
    """Write a row."""
    conn.execute("DELETE FROM thing WHERE a = ?", (1,))
'''


def one(text: str) -> list[SourceFile]:
    return [make_source("tariffpeg/store/thing.py", text)]


def test_every_query_in_the_real_store_says_its_order() -> None:
    assert check_flake.problems() == []


def test_an_ordered_query_reads_clean(plant: Planter) -> None:
    plant(check_flake, "package_files", one(ORDERED))
    assert check_flake.problems() == []


def test_an_unordered_query_that_takes_every_row_is_reported(plant: Planter) -> None:
    plant(check_flake, "package_files", one(UNORDERED))
    found = check_flake.problems()
    assert len(found) == 1
    assert "no ordering" in found[0]


def test_an_unordered_query_that_takes_one_row_is_left_alone(plant: Planter) -> None:
    plant(check_flake, "package_files", one(ONE))
    assert check_flake.problems() == []


def test_an_aggregate_is_one_row_by_construction(plant: Planter) -> None:
    plant(check_flake, "package_files", one(COUNTED))
    assert check_flake.problems() == []


def test_a_query_with_a_limit_on_it_says_its_order_well_enough() -> None:
    assert check_flake.is_ordered("SELECT a FROM thing LIMIT 1")
    assert check_flake.is_ordered("SELECT a FROM thing ORDER BY a")
    assert not check_flake.is_ordered("SELECT a FROM thing")


def test_every_aggregate_the_store_uses_is_recognised() -> None:
    for aggregate in check_flake.AGGREGATES:
        assert check_flake.is_ordered(f"SELECT {aggregate}a) FROM thing")


def test_a_query_built_out_of_a_format_string_is_still_read(plant: Planter) -> None:
    text = FORMATTED
    plant(check_flake, "package_files", one(text))
    assert len(check_flake.problems()) == 1


def test_a_query_built_by_joining_two_strings_is_still_read(plant: Planter) -> None:
    text = JOINED
    plant(check_flake, "package_files", one(text))
    assert len(check_flake.problems()) == 1


def test_something_that_is_not_a_query_is_left_alone(plant: Planter) -> None:
    text = NOT_A_QUERY
    plant(check_flake, "package_files", one(text))
    assert check_flake.problems() == []


def test_the_check_exits_nothing_on_a_clean_tree() -> None:
    assert check_flake.main() == 0


def test_the_check_exits_one_when_it_finds_something(plant: Planter) -> None:
    plant(check_flake, "package_files", one(UNORDERED))
    assert check_flake.main() == 1
