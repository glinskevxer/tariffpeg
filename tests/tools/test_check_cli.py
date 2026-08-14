"""The only documentation anybody reads is what comes back from typing help."""

from __future__ import annotations

from tariffpeg.tools import check_cli
from tariffpeg.tools.walk import SourceFile
from tests.tools.conftest import Planter, make_source

GOOD = '''"""A command line module."""

import click


@click.group(name="thing")
def thing_group() -> None:
    """Look after the things."""


@thing_group.command(name="add")
@click.argument("ref")
@click.option("--why", default="", help="Why this is being added.")
@click.option("--yes", is_flag=True)
def add_command(ref: str, why: str, yes: bool) -> None:
    """Put a thing on the register."""
'''
ENTRY = '''"""The entry point."""

from tariffpeg.cli.thing import thing_group

main.add_command(thing_group)
'''


def files(*texts: tuple[str, str]) -> list[SourceFile]:
    return [make_source(name, text) for name, text in texts]


def test_the_real_command_line_explains_itself() -> None:
    assert check_cli.problems() == []


def test_a_module_that_explains_itself_reads_clean(plant: Planter) -> None:
    plant(
        check_cli,
        "package_files",
        files(("tariffpeg/cli/thing.py", GOOD), ("tariffpeg/cli/main.py", ENTRY)),
    )
    assert check_cli.problems() == []


def test_an_option_with_no_help_is_reported(plant: Planter) -> None:
    text = GOOD.replace(', help="Why this is being added."', "")
    plant(
        check_cli,
        "package_files",
        files(("tariffpeg/cli/thing.py", text), ("tariffpeg/cli/main.py", ENTRY)),
    )
    found = check_cli.problems()
    assert any("takes --why with no help" in problem for problem in found)


def test_the_options_click_writes_the_help_for_are_left_alone(plant: Planter) -> None:
    plant(
        check_cli,
        "package_files",
        files(("tariffpeg/cli/thing.py", GOOD), ("tariffpeg/cli/main.py", ENTRY)),
    )
    assert not any("--yes" in problem for problem in check_cli.problems())


def test_a_command_with_no_docstring_has_no_help_text(plant: Planter) -> None:
    text = GOOD.replace('    """Put a thing on the register."""', "    pass")
    plant(
        check_cli,
        "package_files",
        files(("tariffpeg/cli/thing.py", text), ("tariffpeg/cli/main.py", ENTRY)),
    )
    assert any("add_command has no help text" in problem for problem in check_cli.problems())


def test_a_group_nobody_registers_is_reported(plant: Planter) -> None:
    plant(
        check_cli,
        "package_files",
        files(("tariffpeg/cli/thing.py", GOOD), ("tariffpeg/cli/main.py", '"""x."""\n')),
    )
    found = check_cli.problems()
    assert found == ["src/tariffpeg/cli/thing.py defines thing_group, which nothing registers"]


def test_a_module_outside_the_command_line_is_left_alone(plant: Planter) -> None:
    text = GOOD.replace(', help="Why this is being added."', "")
    plant(check_cli, "package_files", files(("tariffpeg/store/thing.py", text)))
    assert check_cli.problems() == []


def test_an_argument_is_not_an_option_and_needs_no_help(plant: Planter) -> None:
    plant(
        check_cli,
        "package_files",
        files(("tariffpeg/cli/thing.py", GOOD), ("tariffpeg/cli/main.py", ENTRY)),
    )
    assert not any("ref" in problem for problem in check_cli.problems())


def test_the_check_exits_nothing_on_a_clean_tree() -> None:
    assert check_cli.main() == 0


def test_the_check_exits_one_when_it_finds_something(plant: Planter) -> None:
    plant(
        check_cli,
        "package_files",
        files(("tariffpeg/cli/thing.py", GOOD), ("tariffpeg/cli/main.py", '"""x."""\n')),
    )
    assert check_cli.main() == 1


def test_a_decorator_that_is_not_a_plain_name_is_left_alone(plant: Planter) -> None:
    text = (
        chr(34) * 3
        + "x."
        + chr(34) * 3
        + chr(10) * 2
        + "DECORATORS = {}"
        + chr(10) * 2
        + '@DECORATORS["command"]'
        + chr(10)
        + "def show_command() -> None:"
        + chr(10)
        + '    """Show a thing."""'
        + chr(10)
    )
    plant(check_cli, "package_files", [make_source("tariffpeg/cli/x.py", text)])
    assert check_cli.problems() == []
