"""The first thing somebody does with a name they did not write is hover over it."""

from __future__ import annotations

from tariffpeg.tools import check_docstrings
from tests.tools.conftest import Planter, make_source

GOOD = '''"""A module that says what it is for."""


class Thing:
    """A class that says what it is for."""

    def method(self) -> None:
        """Do the thing this method is for."""

    def _private(self) -> None:
        pass


def helper() -> None:
    """Do the thing this function is for."""


def _hidden() -> None:
    pass
'''
WITH_DUNDER = (
    GOOD
    + '''

class Other:
    """Another class that says what it is for."""

    def __repr__(self) -> str:
        return "x"
'''
)


def test_the_real_tree_has_a_docstring_on_everything_public() -> None:
    assert check_docstrings.problems() == []


def test_a_file_that_is_all_documented_reads_clean(plant: Planter) -> None:
    plant(check_docstrings, "source_files", [make_source("tariffpeg/x.py", GOOD)])
    assert check_docstrings.problems() == []


def test_a_module_with_no_docstring_is_reported(plant: Planter) -> None:
    plant(check_docstrings, "source_files", [make_source("tariffpeg/x.py", "A = 1\n")])
    assert check_docstrings.problems() == ["src/tariffpeg/x.py has no module docstring"]


def test_a_public_function_with_no_docstring_is_reported(plant: Planter) -> None:
    text = GOOD.replace('    """Do the thing this function is for."""', "    pass")
    plant(check_docstrings, "source_files", [make_source("tariffpeg/x.py", text)])
    assert any("helper has no docstring" in problem for problem in check_docstrings.problems())


def test_a_public_class_with_no_docstring_is_reported(plant: Planter) -> None:
    text = GOOD.replace('    """A class that says what it is for."""\n\n', "")
    plant(check_docstrings, "source_files", [make_source("tariffpeg/x.py", text)])
    assert any("Thing has no docstring" in problem for problem in check_docstrings.problems())


def test_a_token_docstring_is_reported(plant: Planter) -> None:
    text = GOOD.replace('"""Do the thing this function is for."""', '"""x."""')
    plant(check_docstrings, "source_files", [make_source("tariffpeg/x.py", text)])
    assert any("token docstring" in problem for problem in check_docstrings.problems())


def test_a_private_helper_is_left_alone(plant: Planter) -> None:
    plant(check_docstrings, "source_files", [make_source("tariffpeg/x.py", GOOD)])
    found = check_docstrings.problems()
    assert not any("_hidden" in problem for problem in found)
    assert not any("_private" in problem for problem in found)


def test_a_dunder_method_is_left_alone(plant: Planter) -> None:
    plant(check_docstrings, "source_files", [make_source("tariffpeg/x.py", WITH_DUNDER)])
    assert not any("__repr__" in problem for problem in check_docstrings.problems())


def test_the_public_names_in_a_file_can_be_listed() -> None:
    assert check_docstrings.describe(make_source("tariffpeg/x.py", GOOD)) == ["Thing", "helper"]


def test_the_check_exits_nothing_on_a_clean_tree() -> None:
    assert check_docstrings.main() == 0


def test_the_check_exits_one_when_it_finds_something(plant: Planter) -> None:
    plant(check_docstrings, "source_files", [make_source("tariffpeg/x.py", "A = 1\n")])
    assert check_docstrings.main() == 1
