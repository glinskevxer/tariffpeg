"""Every public module, class and function says what it is for.

A private helper does not need one. Everything a caller in another module can
reach does, because this package is read by people who did not write it and the
first thing they do is hover over a name.
"""

from __future__ import annotations

import ast
import sys

from tariffpeg.tools.walk import SourceFile, report, source_files

NAME = "check_docstrings"

SHORTEST = 12
"""A docstring shorter than this is a placeholder rather than a sentence."""


def _is_public(name: str) -> bool:
    return not name.startswith("_") or (name.startswith("__") and name.endswith("__"))


def _wants_one(node: ast.FunctionDef | ast.ClassDef) -> bool:
    if not _is_public(node.name):
        return False
    return not (node.name.startswith("__") and node.name.endswith("__"))


def problems() -> list[str]:
    """Return every public thing with no docstring, or a token one."""
    found: list[str] = []
    for source in source_files():
        if not ast.get_docstring(source.tree):
            found.append(f"{source.where} has no module docstring")
        for name, node in source.named():
            if not _wants_one(node):
                continue
            written = ast.get_docstring(node)
            if written is None:
                found.append(f"{source.where}:{node.lineno} {name} has no docstring")
            elif len(written.strip()) < SHORTEST:
                found.append(f"{source.where}:{node.lineno} {name} has a token docstring")
    return found


def describe(source: SourceFile) -> list[str]:
    """Return the public names in one file, for the other checks to use."""
    names: list[str] = []
    for node in source.tree.body:
        if isinstance(node, ast.FunctionDef | ast.ClassDef) and _is_public(node.name):
            names.append(node.name)
    return names


def main() -> int:
    """Run the check and return an exit code."""
    return report(NAME, problems())


if __name__ == "__main__":
    sys.exit(main())
