"""A command that is written and never registered does not appear in the reference."""

from __future__ import annotations

import click

from tariffpeg.cli.main import main as entry_point
from tariffpeg.tools import build_commands
from tariffpeg.tools.document import stale


def test_the_document_on_disk_is_what_the_code_would_write() -> None:
    assert stale(build_commands.DOCUMENT, build_commands.text()) == ""


def test_every_group_on_the_entry_point_has_a_heading() -> None:
    text = build_commands.text()
    assert isinstance(entry_point, click.Group)
    for name in entry_point.commands:
        assert f"## `tariffpeg {name}`" in text


def test_every_command_in_every_group_has_a_heading() -> None:
    text = build_commands.text()
    assert isinstance(entry_point, click.Group)
    for group_name, group in entry_point.commands.items():
        if not isinstance(group, click.Group):
            continue
        for command_name in group.commands:
            assert f"### `tariffpeg {group_name} {command_name}`" in text


def test_a_command_that_sits_outside_a_group_still_gets_a_heading() -> None:
    text = build_commands.text()
    assert isinstance(entry_point, click.Group)
    loose = [
        name
        for name, command in entry_point.commands.items()
        if not isinstance(command, click.Group)
    ]
    assert loose
    for name in loose:
        assert f"## `tariffpeg {name}`" in text


def test_a_command_carries_the_first_line_of_its_help() -> None:
    assert "Put a licence on the register." in build_commands.text()


def test_the_options_of_a_command_are_listed_with_their_help() -> None:
    text = build_commands.text()
    assert "The trading name on the plaque." in text
    assert "`--locality`" in text


def test_a_required_option_is_marked_as_required() -> None:
    lines = [line for line in build_commands.text().splitlines() if "`--property-ref`" in line]
    assert len(lines) == 1
    assert "required" in lines[0]


def test_an_option_that_is_not_required_is_not_marked_as_one() -> None:
    lines = [line for line in build_commands.text().splitlines() if "`--changed-only`" in line]
    assert len(lines) == 1
    assert "required" not in lines[0]


def test_an_argument_is_listed_as_an_argument() -> None:
    lines = [line for line in build_commands.text().splitlines() if "| `ref` |" in line]
    assert any("argument" in line for line in lines)


def test_the_help_option_click_adds_is_not_listed() -> None:
    assert "`--help`" not in build_commands.text()


def test_the_document_says_what_wrote_it() -> None:
    assert "Written by build_commands" in build_commands.text()


def test_the_generator_writes_and_checks_the_document() -> None:
    assert build_commands.main() == 0
