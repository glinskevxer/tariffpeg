"""Every column that points at another table is indexed.

A foreign key with no index on it is fine until somebody deletes a licence, at
which point SQLite scans every review in the store looking for the ones to
cascade. That is quick on a test database and it is not quick on a real one, and
the difference only shows up in front of somebody who is waiting.

The rule is satisfied by an index that starts with the column, or by the column
being the first part of the primary key, because both of those are already the
lookup the delete needs.
"""

from __future__ import annotations

import re
import sys

from tariffpeg.store.migrations import MIGRATIONS
from tariffpeg.tools.walk import report

NAME = "check_indexes"

TABLE = re.compile(r"CREATE TABLE (\w+)\s*\((.*)\)\s*$", re.S | re.I)
INDEX = re.compile(r"CREATE (?:UNIQUE )?INDEX (\w+) ON (\w+)\s*\(([^)]*)\)", re.I)
REFERENCES = re.compile(r"^\s*(\w+)\s+\w+.*REFERENCES\s+(\w+)", re.I)
PRIMARY_KEY = re.compile(r"PRIMARY KEY\s*\(([^)]*)\)", re.I)


def _first_column(listed: str) -> str:
    return listed.split(",")[0].strip().split()[0]


def read_schema() -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, str]]:
    """Return the pointing columns, the indexed columns and the leading key column."""
    pointing: dict[str, list[str]] = {}
    indexed: dict[str, list[str]] = {}
    leading: dict[str, str] = {}
    for migration in MIGRATIONS:
        for statement in migration.statements:
            table = TABLE.search(statement.strip())
            if table:
                name, body = table.group(1), table.group(2)
                for line in body.splitlines():
                    pointer = REFERENCES.match(line)
                    if pointer:
                        pointing.setdefault(name, []).append(pointer.group(1))
                key = PRIMARY_KEY.search(body)
                if key:
                    leading[name] = _first_column(key.group(1))
                else:
                    for line in body.splitlines():
                        if "PRIMARY KEY" in line.upper():
                            leading[name] = line.strip().split()[0]
                            break
            for index in INDEX.finditer(statement):
                indexed.setdefault(index.group(2), []).append(_first_column(index.group(3)))
    return pointing, indexed, leading


def problems() -> list[str]:
    """Return every pointing column with nothing to look it up by."""
    pointing, indexed, leading = read_schema()
    found: list[str] = []
    for table, columns in sorted(pointing.items()):
        for column in columns:
            if column in indexed.get(table, []):
                continue
            if leading.get(table) == column:
                continue
            found.append(f"{table}.{column} points at another table with no index on it")
    return found


def main() -> int:
    """Run the check and return an exit code."""
    return report(NAME, problems())


if __name__ == "__main__":
    sys.exit(main())
