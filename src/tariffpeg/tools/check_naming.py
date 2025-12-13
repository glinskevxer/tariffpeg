"""Test names say what is true, not what is being poked.

A name like ``test_licence_works`` is the name of a test nobody can read the
failure of. The one below it says what the code is supposed to do, so a red line
in the output is already a sentence about what broke.

The vague words are the ones that turned up in this repository and were replaced
with something that said more.
"""

from __future__ import annotations

import ast
import sys

from tariffpeg.tools.walk import report, suite_files

NAME = "check_naming"

LEAST_WORDS = 5
"""How many words a test name carries after the prefix."""

VAGUE = frozenset(
    {
        "works",
        "correct",
        "correctly",
        "good",
        "bad",
        "ok",
        "okay",
        "stuff",
        "thing",
        "things",
        "basic",
        "simple",
        "various",
        "properly",
        "handles",
        "handled",
    }
)
"""Words that say nothing about what is supposed to be true.

These are the ones that turned up here and were replaced. Words that read as
vague elsewhere are not on the list when they mean something in this domain: a
case file is a case file, and an attribute test is an attribute test."""


def words_of(name: str) -> list[str]:
    """Return the words in a test name, without the prefix."""
    return name.removeprefix("test_").split("_")


def problems() -> list[str]:
    """Return every test whose name does not say what is true."""
    found: list[str] = []
    for source in suite_files():
        if not source.path.name.startswith("test_"):
            continue
        if not ast.get_docstring(source.tree):
            found.append(f"{source.where} has no module docstring")
        for node in source.tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            if not node.name.startswith("test_"):
                continue
            words = words_of(node.name)
            if len(words) < LEAST_WORDS:
                found.append(
                    f"{source.where}:{node.lineno} {node.name} is {len(words)} words,"
                    f" fewer than {LEAST_WORDS}"
                )
            for word in words:
                if word in VAGUE:
                    found.append(
                        f"{source.where}:{node.lineno} {node.name} says {word!r},"
                        " which says nothing"
                    )
    return found


def main() -> int:
    """Run the check and return an exit code."""
    return report(NAME, problems())


if __name__ == "__main__":
    sys.exit(main())
