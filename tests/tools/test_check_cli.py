"""The only documentation anybody reads is what two dashes and help print."""

from __future__ import annotations

from tariffpeg.tools import check_cli
from tariffpeg.tools.walk import SourceFile
from tests.tools.conftest import Planter, make_source

ENTRY = '''"""The entry point."""

main.add_command(thing_group)
'''


def command(body: str, relative: str = "tariffpeg/cli/x.py") -> SourceFile:
    return make_source(relative, f'"""x."""\n\n{body}')


GOOD = '''@thing_group.command(name="do")
@click.option("--why", default="", help="Why this is being done.")
def do_command(ctx: Context) -> None:
    """Do the thing."""
'''
GROUP = '''@click.group(name="thing")
def thing_group() -> None:
    """Look after the things."""
'''


def test_the_real_command_line_explains_itself() -> None:
    assert check_cli.problems() == []


def test_a_command_with_help_on_every_option_reads_clean(plant: Planter) -> None:
    plant(check_cli, "package_files", [command(GOOD), command(ENTRY, "tariffpeg/cli/main.py")])
    assert check_cli.problems() == []


def test_an_option_with_no_help_is_reported(plant: Planter) -> None:
    body = GOOD.replace(', help="Why this is being done."', "")
    plant(check_cli, "package_files", [command(body), command(ENTRY, "tariffpeg/cli/main.py")])
    found = check_cli.problems()
    assert len(found) == 1
    assert "do_command takes --why with no help" in found[0]


def test_a_command_with_no_help_text_is_reported(plant: Planter) -> None:
    body = GOOD.replace('    """Do the thing."""', "    pass")
    plant(check_cli, "package_files", [command(body), command(ENTRY, "tariffpeg/cli/main.py")])
    assert any("has no help text" in problem for problem in check_cli.problems())


def test_the_options_click_writes_itself_are_left_alone(plant: Planter) -> None:
    body = GOOD.replace(
        '@click.option("--why", default="", help="Why this is being done.")',
        '@click.confirmation_option("--yes")',
    )
    plant(check_cli, "package_files", [command(body), command(ENTRY, "tariffpeg/cli/main.py")])
    assert check_cli.problems() == []


def test_an_argument_is_not_an_option_and_needs_no_help(plant: Planter) -> None:
    body = GOOD.replace(
        '@click.option("--why", default="", help="Why this is being done.")',
        '@click.argument("ref")',
    )
    plant(check_cli, "package_files", [command(body), command(ENTRY, "tariffpeg/cli/main.py")])
    assert check_cli.problems() == []


def test_a_group_nobody_registers_is_reported(plant: Planter) -> None:
    entry = command('"""The entry point."""\n', "tariffpeg/cli/main.py")
    plant(check_cli, "package_files", [command(GROUP), entry])
    found = check_cli.problems()
    assert found == ["src/tariffpeg/cli/x.py defines thing_group, which nothing registers"]


def test_a_group_that_is_registered_reads_clean(plant: Planter) -> None:
    plant(check_cli, "package_files", [command(GROUP), command(ENTRY, "tariffpeg/cli/main.py")])
    assert check_cli.problems() == []


def test_a_module_outside_the_command_line_is_left_alone(plant: Planter) -> None:
    plant(check_cli, "package_files", [command(GROUP, "tariffpeg/store/x.py")])
    assert check_cli.problems() == []


def test_a_plain_function_in_a_command_module_is_left_alone(plant: Planter) -> None:
    body = 'def helper() -> None:\n    """Do something."""\n'
    plant(check_cli, "package_files", [command(body), command(ENTRY, "tariffpeg/cli/main.py")])
    assert check_cli.problems() == []


def test_every_group_the_real_entry_point_registers_is_a_real_group() -> None:
    from tariffpeg.cli.main import main

    assert "harvest" in main.commands
    assert "case" in main.commands


def test_the_check_exits_nothing_on_a_clean_tree() -> None:
    assert check_cli.main() == 0
