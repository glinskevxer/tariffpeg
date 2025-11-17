"""A check with its own allow list goes quiet the first time somebody adds to it."""

from __future__ import annotations

from tariffpeg.tools import check_sql
from tariffpeg.tools.walk import SourceFile
from tests.tools.conftest import Planter, make_source

GOOD = '''"""A store."""

COLUMNS = ("a", "b")
PLACEHOLDERS = "?, ?"


def add(conn: object, values: tuple[str, ...]) -> None:
    """Write a row."""
    conn.execute(f"INSERT INTO thing ({', '.join(COLUMNS)}) VALUES ({PLACEHOLDERS})", values)
'''


def one(text: str) -> list[SourceFile]:
    return [make_source("tariffpeg/store/thing.py", text)]


def test_the_real_store_only_interpolates_its_own_constants() -> None:
    assert check_sql.problems() == []


def test_a_statement_built_from_module_constants_reads_clean(plant: Planter) -> None:
    plant(check_sql, "package_files", one(GOOD))
    assert check_sql.problems() == []


def test_a_statement_built_from_something_that_arrived_is_reported(plant: Planter) -> None:
    text = GOOD.replace("{PLACEHOLDERS}", "{values}")
    plant(check_sql, "package_files", one(text))
    found = check_sql.problems()
    assert len(found) == 1
    assert "out of values" in found[0]


def test_a_statement_built_from_a_local_is_reported(plant: Planter) -> None:
    extra = '    wanted = "x"\n    conn.execute(f"INSERT INTO {wanted} VALUES (1)")\n'
    text = GOOD.replace('    conn.execute(f"INSERT', extra + '    conn.execute(f"INSERT')
    plant(check_sql, "package_files", one(text))
    assert any("out of wanted" in problem for problem in check_sql.problems())


def test_a_message_that_is_not_a_statement_is_left_alone(plant: Planter) -> None:
    text = (
        '"""A store."""\n\n\ndef f(name: str) -> str:\n    """x."""\n    return f"no {name} here"\n'
    )
    plant(check_sql, "package_files", one(text))
    assert check_sql.problems() == []


def test_an_annotated_constant_counts_as_one(plant: Planter) -> None:
    text = GOOD.replace('PLACEHOLDERS = "?, ?"', 'PLACEHOLDERS: str = "?, ?"')
    plant(check_sql, "package_files", one(text))
    assert check_sql.problems() == []


def test_a_constant_reached_through_an_attribute_is_read_by_its_root(plant: Planter) -> None:
    text = GOOD.replace("{PLACEHOLDERS}", "{COLUMNS.count}")
    plant(check_sql, "package_files", one(text))
    assert check_sql.problems() == []


def test_the_keywords_that_make_a_string_a_statement_are_recognised() -> None:
    assert check_sql.looks_like_sql("select a from b")
    assert check_sql.looks_like_sql("DELETE FROM thing")
    assert check_sql.looks_like_sql("CREATE INDEX x ON y(z)")
    assert not check_sql.looks_like_sql("nothing to see")


def test_the_constants_in_a_file_are_read_off_the_module() -> None:
    found = check_sql.module_constants(make_source("tariffpeg/store/thing.py", GOOD))
    assert found == {"COLUMNS", "PLACEHOLDERS"}


def test_the_check_exits_nothing_on_a_clean_tree() -> None:
    assert check_sql.main() == 0


def test_the_check_exits_one_when_it_finds_something(plant: Planter) -> None:
    plant(check_sql, "package_files", one(GOOD.replace("{PLACEHOLDERS}", "{values}")))
    assert check_sql.main() == 1
