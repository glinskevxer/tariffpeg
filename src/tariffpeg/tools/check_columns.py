"""Every printed row carries exactly the keys its columns ask for.

A table is two things written in two places: a tuple of columns saying what the
headings are and which are numbers, and a dictionary built somewhere else saying
what goes under them. Nothing makes the two agree. A column whose key nothing
produces prints as an empty stripe down the table, and a key nothing declares is
worked out and then thrown away.

Both have happened here. Neither shows up in a test unless the test asserts on
that one column, and a test that renders a table and checks it is not empty
passes through both.

The check does not guess. It reads the ``Column`` calls in a module, and it only
looks at dictionaries that already share at least two keys with one of those
column sets. A dictionary that has nothing to do with a table cannot reach that
bar, and one that does is a row.

A module that prints several tables has several column sets, and a row is
measured against the one it overlaps most. A row that overlaps two of them
equally is left alone, because there is no way to tell from the source which
table it was written for and a guess here would be a false report every time.
"""

from __future__ import annotations

import ast
import sys

from tariffpeg.tools.walk import SourceFile, package_files, report

NAME = "check_columns"

COLUMN = "Column"
"""The call whose first argument is a column key."""

SHARED_KEYS = 2
"""How many keys a dictionary shares with a column set before it counts as a row."""


def column_sets(source: SourceFile) -> list[tuple[int, frozenset[str]]]:
    """Return each tuple of columns in a file, as the keys it declares."""
    found: list[tuple[int, frozenset[str]]] = []
    for node in ast.walk(source.tree):
        if not isinstance(node, ast.Tuple | ast.List):
            continue
        keys = [_column_key(item) for item in node.elts]
        if keys and all(key for key in keys):
            found.append((node.lineno, frozenset(key for key in keys if key)))
    return found


def _column_key(node: ast.expr) -> str:
    """Return the key a ``Column`` call declares, or the empty string."""
    if not isinstance(node, ast.Call):
        return ""
    called = node.func
    name = called.attr if isinstance(called, ast.Attribute) else getattr(called, "id", "")
    if name != COLUMN or not node.args:
        return ""
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return ""


def row_keys(node: ast.Dict) -> frozenset[str]:
    """Return the keys of a dictionary written out in full, or nothing.

    A dictionary with a computed key or a double star in it is not a row this
    check can read, and reading it half way would report a row as missing a key
    that the star puts in.
    """
    keys: list[str] = []
    for key in node.keys:
        if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
            return frozenset()
        keys.append(key.value)
    return frozenset(keys)


def nearest(keys: frozenset[str], declared_sets: list[frozenset[str]]) -> frozenset[str] | None:
    """Return the column set a row was most likely written for, if one stands out."""
    scored = [(len(keys & declared), declared) for declared in declared_sets]
    best = max((count for count, _ in scored), default=0)
    if best < SHARED_KEYS:
        return None
    tied = [declared for count, declared in scored if count == best]
    if len({tuple(sorted(declared)) for declared in tied}) != 1:
        return None
    return tied[0]


def mismatches(source: SourceFile) -> list[str]:
    """Return every row in a file that does not match the columns it prints under."""
    sets = column_sets(source)
    if not sets:
        return []
    found: list[str] = []
    declared_sets = [declared for _, declared in sets]
    for node in ast.walk(source.tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = row_keys(node)
        if not keys:
            continue
        declared = nearest(keys, declared_sets)
        if declared is None or keys == declared:
            continue
        missing = sorted(declared - keys)
        extra = sorted(keys - declared)
        if missing:
            found.append(
                f"{source.where}:{node.lineno} a row prints under columns"
                f" it has no {', '.join(missing)} for"
            )
        if extra:
            found.append(
                f"{source.where}:{node.lineno} a row carries {', '.join(extra)},"
                " which no column prints"
            )
    return found


def problems() -> list[str]:
    """Return every row in the tree that does not match its columns."""
    found: list[str] = []
    for source in package_files():
        found.extend(mismatches(source))
    return found


def main() -> int:
    """Run the check and return an exit code."""
    return report(NAME, problems())


if __name__ == "__main__":
    sys.exit(main())
