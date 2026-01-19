"""Every selector handed to the compiler as a literal actually compiles.

A selector in a profile is checked when the profile is registered. One written
into a module as a constant is not, until the day it is used, which is halfway
through a harvest.

This does not guess at which strings are selectors. It reads the calls, which is
exact: a literal passed to the compiler is a selector, and nothing else is.
"""

from __future__ import annotations

import ast
import sys

from tariffpeg.errors import Invalid
from tariffpeg.parse.select import compile_selector
from tariffpeg.tools.walk import SourceFile, package_files, report

NAME = "check_selectors"

COMPILERS = frozenset({"compile_selector"})
"""The functions whose literal arguments are selectors."""


def literal_selectors(source: SourceFile) -> list[tuple[int, str]]:
    """Return every selector this file hands to the compiler as a literal."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(source.tree):
        if not isinstance(node, ast.Call):
            continue
        called = node.func
        name = called.attr if isinstance(called, ast.Attribute) else getattr(called, "id", "")
        if name not in COMPILERS or not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            found.append((node.lineno, first.value))
    return found


def problems() -> list[str]:
    """Return every selector in the tree that will not compile."""
    found: list[str] = []
    for source in package_files():
        for line, selector in literal_selectors(source):
            try:
                compile_selector(selector)
            except Invalid as err:
                found.append(f"{source.where}:{line} {selector!r} will not compile: {err.reason}")
    return found


def main() -> int:
    """Run the check and return an exit code."""
    return report(NAME, problems())


if __name__ == "__main__":
    sys.exit(main())
