"""A query whose rows get iterated says what order they come in.

SQLite will hand back rows in whatever order suits it, and on a small test
database that order is almost always insertion order, which is almost always the
order the test expected. The same query on a real store, after a delete and a
vacuum, comes back differently, and the test that has passed a thousand times
fails once on somebody machine.

So the rule is mechanical: a statement with no ordering on it may be fetched one
row at a time and no other way. Aggregates are exempt because they are one row
by construction.
"""

from __future__ import annotations

import ast
import sys

from tariffpeg.tools.walk import package_files, report

NAME = "check_flake"

AGGREGATES = ("count(", "sum(", "max(", "min(", "avg(", "length(")
"""What makes a statement one row whatever the table holds."""

ONE_ROW = ("fetchone",)
"""The ways of taking a single row."""


def _sql_of(node: ast.Call) -> str:
    if not node.args:
        return ""
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    if isinstance(first, ast.JoinedStr):
        return "".join(
            part.value
            for part in first.values
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
        )
    if isinstance(first, ast.BinOp):
        return _sql_of_expression(first)
    return ""


def _sql_of_expression(node: ast.expr) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            part.value
            for part in node.values
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
        )
    if isinstance(node, ast.BinOp):
        return _sql_of_expression(node.left) + _sql_of_expression(node.right)
    return ""


def is_ordered(sql: str) -> bool:
    """Return whether a statement says what order its rows come in."""
    upper = sql.upper()
    if "ORDER BY" in upper or " LIMIT " in upper:
        return True
    return any(word in sql.lower() for word in AGGREGATES)


def _single_row_calls(tree: ast.Module) -> set[int]:
    """Return the ids of the execute calls whose result is taken one row at a time.

    The shape looked for is ``conn.execute(...).fetchone()``, where the execute
    call is the thing the attribute hangs off. Walking up from the execute call
    to find its parent would land on the attribute rather than the call, which
    is how the first version of this check reported every lookup in the store.
    """
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in ONE_ROW:
            continue
        inner = node.func.value
        if isinstance(inner, ast.Call):
            found.add(id(inner))
    return found


def problems() -> list[str]:
    """Return every unordered statement whose rows are taken more than one at a time."""
    found: list[str] = []
    for source in package_files():
        single = _single_row_calls(source.tree)
        for node in ast.walk(source.tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr != "execute":
                continue
            sql = _sql_of(node)
            if "SELECT" not in sql.upper() or is_ordered(sql):
                continue
            if id(node) in single:
                continue
            found.append(
                f"{source.where}:{node.lineno} runs a statement with no ordering"
                " and does not take one row"
            )
    return found


def main() -> int:
    """Run the check and return an exit code."""
    return report(NAME, problems())


if __name__ == "__main__":
    sys.exit(main())
