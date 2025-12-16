"""Write the schema document out of the migrations that build it."""

from __future__ import annotations

import re
import sys

from tariffpeg.store.migrations import MIGRATIONS
from tariffpeg.tools.document import render, run, table

NAME = "schema_dump"
DOCUMENT = "schema.md"

TABLE = re.compile(r"CREATE TABLE (\w+)\s*\((.*)\)\s*$", re.S | re.I)
INDEX = re.compile(r"CREATE (UNIQUE )?INDEX (\w+) ON (\w+)\s*\(([^)]*)\)", re.I)


def _columns(body: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw in body.splitlines():
        line = raw.strip().rstrip(",")
        if not line or line.upper().startswith("PRIMARY KEY"):
            continue
        parts = line.split()
        name, kind = parts[0], parts[1] if len(parts) > 1 else ""
        rest = " ".join(parts[2:])
        rows.append([f"`{name}`", kind, rest or " "])
    return rows


def body() -> list[str]:
    """Return the lines of the schema document."""
    lines: list[str] = []
    for migration in MIGRATIONS:
        lines.append(f"## {migration.number:03d} {migration.name}")
        lines.append("")
        lines.append(f"Digest `{migration.digest}`.")
        lines.append("")
        indexes: list[list[str]] = []
        for statement in migration.statements:
            found = TABLE.search(statement.strip())
            if found:
                lines.append(f"### `{found.group(1)}`")
                lines.append("")
                lines.extend(table(["column", "type", "and"], _columns(found.group(2))))
                lines.append("")
            for index in INDEX.finditer(statement):
                unique = "yes" if index.group(1) else "no"
                indexes.append(
                    [f"`{index.group(2)}`", f"`{index.group(3)}`", index.group(4), unique]
                )
        if indexes:
            lines.append("### indexes")
            lines.append("")
            lines.extend(table(["index", "on", "columns", "unique"], indexes))
            lines.append("")
    return lines


def text() -> str:
    """Return the whole schema document."""
    return render(NAME, "Schema", body())


def main() -> int:
    """Write the document, or check it, and return an exit code."""
    return run(NAME, DOCUMENT, text())


if __name__ == "__main__":
    sys.exit(main())
