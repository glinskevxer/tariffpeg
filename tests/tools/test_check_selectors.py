"""A selector written into a module is not checked until halfway through a harvest."""

from __future__ import annotations

from tariffpeg.tools import check_selectors
from tariffpeg.tools.walk import SourceFile
from tests.tools.conftest import Planter, make_source

GOOD = '''"""x."""

from tariffpeg.parse.select import compile_selector

SCRIPT = compile_selector("article.review > p.body")
'''
THROUGH_MODULE = '''"""x."""

from tariffpeg.parse import select

SCRIPT = select.compile_selector("a:hover")
'''
NOT_A_LITERAL = '''"""x."""

from tariffpeg.parse.select import compile_selector


def read(written: str) -> object:
    """Compile whatever it is handed."""
    return compile_selector(written)
'''
NO_ARGUMENTS = '''"""x."""

from tariffpeg.parse.select import compile_selector

SCRIPT = compile_selector
'''


def one(text: str) -> list[SourceFile]:
    return [make_source("tariffpeg/parse/x.py", text)]


def test_every_selector_in_the_real_tree_compiles() -> None:
    assert check_selectors.problems() == []


def test_a_selector_that_compiles_reads_clean(plant: Planter) -> None:
    plant(check_selectors, "package_files", one(GOOD))
    assert check_selectors.problems() == []


def test_a_selector_that_will_not_compile_is_reported(plant: Planter) -> None:
    plant(check_selectors, "package_files", one(GOOD.replace("p.body", "p:hover")))
    found = check_selectors.problems()
    assert len(found) == 1
    assert "pseudo class is not supported" in found[0]


def test_a_selector_reached_through_a_module_name_is_still_checked(plant: Planter) -> None:
    plant(check_selectors, "package_files", one(THROUGH_MODULE))
    assert len(check_selectors.problems()) == 1


def test_a_selector_that_is_not_a_literal_is_left_alone(plant: Planter) -> None:
    plant(check_selectors, "package_files", one(NOT_A_LITERAL))
    assert check_selectors.problems() == []


def test_a_string_that_is_not_handed_to_the_compiler_is_left_alone(plant: Planter) -> None:
    plant(check_selectors, "package_files", one('"""x."""\n\nPATTERN = "a:hover"\n'))
    assert check_selectors.problems() == []


def test_the_literals_handed_to_the_compiler_are_found() -> None:
    found = check_selectors.literal_selectors(make_source("tariffpeg/parse/x.py", GOOD))
    assert [selector for _, selector in found] == ["article.review > p.body"]


def test_a_call_with_no_arguments_is_left_alone(plant: Planter) -> None:
    plant(check_selectors, "package_files", one(NO_ARGUMENTS))
    assert check_selectors.problems() == []


def test_the_check_exits_nothing_on_a_clean_tree() -> None:
    assert check_selectors.main() == 0


def test_the_check_exits_one_when_it_finds_something(plant: Planter) -> None:
    plant(check_selectors, "package_files", one(GOOD.replace("p.body", "p:hover")))
    assert check_selectors.main() == 1
