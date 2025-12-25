"""Write the command reference out of the command line itself.

Walked off the click tree rather than off the source, so a command that is
written and never registered does not appear here, and a command that is
registered under a different name appears under the name people type.
"""

from __future__ import annotations

import sys

import click

from tariffpeg.cli.main import main as entry_point
from tariffpeg.tools.document import render, run, table

NAME = "build_commands"
DOCUMENT = "commands.md"


def _summary(command: click.Command) -> str:
    written = (command.help or "").strip().splitlines()
    return written[0] if written else ""


def _options(command: click.Command) -> list[list[str]]:
    rows: list[list[str]] = []
    for param in command.params:
        if isinstance(param, click.Argument):
            rows.append([f"`{param.name}`", "argument", ""])
            continue
        if not isinstance(param, click.Option):
            continue
        if "--help" in param.opts:
            continue
        flags = ", ".join(f"`{flag}`" for flag in param.opts)
        rows.append([flags, "required" if param.required else "", param.help or ""])
    return rows


def body() -> list[str]:
    """Return the lines of the command reference."""
    lines: list[str] = []
    root = entry_point
    assert isinstance(root, click.Group)
    for group_name in sorted(root.commands):
        group = root.commands[group_name]
        lines.append(f"## `tariffpeg {group_name}`")
        lines.append("")
        lines.append(_summary(group))
        lines.append("")
        if not isinstance(group, click.Group):
            continue
        for command_name in sorted(group.commands):
            command = group.commands[command_name]
            lines.append(f"### `tariffpeg {group_name} {command_name}`")
            lines.append("")
            lines.append(_summary(command))
            lines.append("")
            rows = _options(command)
            if rows:
                lines.extend(table(["what", "and", "why"], rows))
                lines.append("")
    return lines


def text() -> str:
    """Return the whole command reference."""
    return render(NAME, "Commands", body())


def main() -> int:
    """Write the document, or check it, and return an exit code."""
    return run(NAME, DOCUMENT, text())


if __name__ == "__main__":
    sys.exit(main())
