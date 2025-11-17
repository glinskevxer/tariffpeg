"""Nothing reaches a query except through a placeholder or a name in this file.

Every statement in the store is built with an f-string somewhere, because the
column lists are written once and reused. That is fine and it is also exactly
how the other thing happens, so the rule is narrow: an f-string that becomes SQL
may interpolate only names defined at the top of the file it is in. Anything
that arrived from outside goes in as a placeholder.

The list of names is read off the module rather than kept here. A check with its
own allow list goes quiet the first time somebody adds a twelfth constant.
"""

from __future__ import annotations

import ast
import sys

from tariffpeg.tools.walk import SourceFile, package_files, report

NAME = "check_sql"

KEYWORDS = ("SELECT ", "INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "CREATE INDEX")
"""What makes a string look like a statement."""


def looks_like_sql(text: str) -> bool:
    """Return whether a string is a statement rather than a message."""
    upper = text.upper()
    return any(keyword in upper for keyword in KEYWORDS)


def module_constants(source: SourceFile) -> set[str]:
    """Return the names assigned at the top of a file."""
    names: set[str] = set()
    for node in source.tree.body:
        if isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _interpolated(node: ast.JoinedStr) -> list[ast.expr]:
    return [part.value for part in node.values if isinstance(part, ast.FormattedValue)]


def _root_name(expression: ast.expr) -> str:
    while isinstance(expression, ast.Attribute):
        expression = expression.value
    if isinstance(expression, ast.Call):
        return _root_name(expression.func)
    if isinstance(expression, ast.Name):
        return expression.id
    return ""


def _text_of(node: ast.JoinedStr) -> str:
    return "".join(
        part.value
        for part in node.values
        if isinstance(part, ast.Constant) and isinstance(part.value, str)
    )


def problems() -> list[str]:
    """Return every statement that interpolates something from outside the file."""
    found: list[str] = []
    for source in package_files():
        constants = module_constants(source)
        for node in ast.walk(source.tree):
            if not isinstance(node, ast.JoinedStr):
                continue
            if not looks_like_sql(_text_of(node)):
                continue
            for expression in _interpolated(node):
                name = _root_name(expression)
                if name and name not in constants:
                    found.append(
                        f"{source.where}:{node.lineno} builds a statement out of {name},"
                        " which is not a constant in this file"
                    )
    return found


def main() -> int:
    """Run the check and return an exit code."""
    return report(NAME, problems())


if __name__ == "__main__":
    sys.exit(main())
