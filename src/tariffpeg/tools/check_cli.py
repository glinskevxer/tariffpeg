"""The command line explains itself.

Every option carries help, because the only documentation anybody reads is what
comes back from typing the command with two dashes and help on the end. Every
group is registered, because a group that is written and never added to the
entry point is a group nobody can reach and nothing else would notice.
"""

from __future__ import annotations

import ast
import sys

from tariffpeg.tools.walk import PACKAGE, SourceFile, package_files, report

NAME = "check_cli"

ENTRY = f"{PACKAGE}.cli.main"
"""The module every group has to be registered on."""

NO_HELP_WANTED = frozenset({"--help", "--version", "--yes"})
"""Options click writes the help for itself."""


def _decorator_name(decorator: ast.expr) -> str:
    call = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(call, ast.Attribute):
        return call.attr
    if isinstance(call, ast.Name):
        return call.id
    return ""


def _option_flags(decorator: ast.Call) -> list[str]:
    return [
        arg.value
        for arg in decorator.args
        if isinstance(arg, ast.Constant)
        and isinstance(arg.value, str)
        and arg.value.startswith("-")
    ]


def _has_help(decorator: ast.Call) -> bool:
    return any(keyword.arg == "help" for keyword in decorator.keywords)


def _commands(source: SourceFile) -> list[tuple[str, ast.FunctionDef]]:
    found: list[tuple[str, ast.FunctionDef]] = []
    for node in source.tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if _decorator_name(decorator) in ("command", "group"):
                found.append((node.name, node))
                break
    return found


def _groups_registered(files: list[SourceFile]) -> set[str]:
    for source in files:
        if source.module != ENTRY:
            continue
        return {
            node.args[0].id
            for node in ast.walk(source.tree)
            if isinstance(node, ast.Call)
            and _decorator_name(node) == "add_command"
            and node.args
            and isinstance(node.args[0], ast.Name)
        }
    return set()


def problems() -> list[str]:
    """Return every option with no help and every group nobody registered."""
    files = package_files()
    registered = _groups_registered(files)
    found: list[str] = []
    for source in files:
        if source.layer != "cli":
            continue
        for name, node in _commands(source):
            if not ast.get_docstring(node):
                found.append(f"{source.where}:{node.lineno} {name} has no help text")
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                if _decorator_name(decorator) != "option":
                    continue
                flags = _option_flags(decorator)
                if not flags or set(flags) & NO_HELP_WANTED:
                    continue
                if not _has_help(decorator):
                    found.append(
                        f"{source.where}:{decorator.lineno} {name} takes {flags[0]} with no help"
                    )
            if name.endswith("_group") and source.module != ENTRY and name not in registered:
                found.append(f"{source.where} defines {name}, which nothing registers")
    return found


def main() -> int:
    """Run the check and return an exit code."""
    return report(NAME, problems())


if __name__ == "__main__":
    sys.exit(main())
