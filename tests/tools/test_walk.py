"""A check that reaches through this module cannot be pointed anywhere else."""

from __future__ import annotations

from tariffpeg.tools import walk
from tests.tools.conftest import make_source, make_test

SMALL = '''"""x."""


class A:
    def b(self) -> None:
        pass


def c() -> None:
    pass
'''
NESTED = (
    SMALL
    + """

def outer() -> None:
    def inner() -> None:
        pass
"""
)


def test_the_repository_root_is_the_directory_with_the_project_file() -> None:
    assert (walk.repo_root() / "pyproject.toml").exists()
    assert walk.source_root().name == "tariffpeg"
    assert walk.suite_root().name == "tests"


def test_every_file_in_the_package_is_found() -> None:
    modules = {found.module for found in walk.source_files()}
    assert "tariffpeg.errors" in modules
    assert "tariffpeg.store.db" in modules
    assert "tariffpeg" in modules


def test_the_suite_is_found_as_well() -> None:
    modules = {found.module for found in walk.suite_files()}
    assert "tests.test_errors" in modules


def test_the_tools_are_left_out_of_the_package_listing() -> None:
    layers = {found.layer for found in walk.package_files()}
    assert "tools" not in layers
    assert "store" in layers


def test_a_module_knows_which_layer_it_sits_in() -> None:
    assert make_source("tariffpeg/store/db.py", '"""x."""\n').layer == "store"
    assert make_source("tariffpeg/errors.py", '"""x."""\n').layer == ""


def test_the_path_a_check_prints_uses_forward_slashes() -> None:
    found = make_source("tariffpeg/store/db.py", '"""x."""\n')
    assert found.where == "src/tariffpeg/store/db.py"


def test_the_functions_and_classes_in_a_file_are_found() -> None:
    found = make_source("tariffpeg/x.py", SMALL)
    assert [node.name for node in found.classes()] == ["A"]
    assert sorted(node.name for node in found.functions()) == ["b", "c"]
    assert len(found.top_level()) == 3


def test_the_names_a_caller_can_reach_leave_out_nested_functions() -> None:
    found = make_source("tariffpeg/x.py", NESTED)
    assert [name for name, _ in found.named()] == ["A", "A.b", "c", "outer"]


def test_the_imports_in_a_file_are_found() -> None:
    text = '"""x."""\n\nimport ast\nfrom pathlib import Path\nfrom tariffpeg.store import db\n'
    found = make_source("tariffpeg/x.py", text)
    assert found.imports() == ["ast", "pathlib", "tariffpeg.store"]


def test_a_top_level_constant_can_be_read_back() -> None:
    text = '"""x."""\n\nCOLUMNS = ("a", "b")\nOTHER: int = 4\n'
    found = make_source("tariffpeg/x.py", text)
    assert found.constant("COLUMNS") is not None
    assert found.constant("OTHER") is not None
    assert found.constant("MISSING") is None


def test_the_lines_of_a_file_come_back_split() -> None:
    found = make_source("tariffpeg/x.py", '"""x."""\nA = 1\n')
    assert found.lines() == ['"""x."""', "A = 1"]


def test_a_test_file_is_named_the_way_the_suite_sees_it() -> None:
    assert make_test("tests/store/test_db.py", '"""x."""\n').module == "tests.store.test_db"


def test_a_package_init_reads_as_the_package_itself() -> None:
    assert make_source("tariffpeg/store/__init__.py", '"""x."""\n').module == "tariffpeg.store"


def test_a_clean_report_says_so_and_exits_nothing() -> None:
    assert walk.report("check_x", []) == 0


def test_a_report_with_problems_lists_them_and_exits_one() -> None:
    assert walk.report("check_x", ["one thing", "another"]) == 1
