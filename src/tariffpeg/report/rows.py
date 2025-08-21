"""Rendering rows, either for a person or for a spreadsheet.

The same rows go both ways. A column is described once, and the table and the
comma separated form are two renderings of that description rather than two
pieces of code that have to be kept in step.

Numbers go right, everything else goes left, and nothing is truncated. A
trading name cut off at twenty characters is a trading name somebody has to go
and look up again.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from tariffpeg.errors import Invalid

MISSING = "-"
"""What is printed where a row has nothing."""


@dataclass(frozen=True, slots=True)
class Column:
    """One column, described once for both renderings."""

    key: str
    title: str
    numeric: bool = False
    places: int = 2

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise Invalid("key", self.key, "a column reads a named field")
        if not self.title.strip():
            raise Invalid("title", self.title, "a column has a heading")
        if self.places < 0:
            raise Invalid("places", self.places, "decimal places are not negative")

    def render(self, value: object) -> str:
        """Return one cell as text."""
        if value is None:
            return MISSING
        if isinstance(value, bool):
            return "yes" if value else "no"
        if isinstance(value, float):
            return f"{value:.{self.places}f}"
        return str(value)


def widths(rows: Sequence[Mapping[str, object]], columns: Sequence[Column]) -> list[int]:
    """Return how wide each column has to be to fit its widest cell."""
    return [
        max(len(column.title), *(len(column.render(row.get(column.key))) for row in rows))
        if rows
        else len(column.title)
        for column in columns
    ]


def render(rows: Sequence[Mapping[str, object]], columns: Sequence[Column]) -> tuple[str, ...]:
    """Return the rows as a table a person reads."""
    if not columns:
        raise Invalid("columns", 0, "a table needs a column in it")
    sizes = widths(rows, columns)
    lines = [_line([c.title for c in columns], columns, sizes)]
    lines.append("  ".join("-" * size for size in sizes))
    for row in rows:
        lines.append(_line([c.render(row.get(c.key)) for c in columns], columns, sizes))
    return tuple(lines)


def _line(cells: Sequence[str], columns: Sequence[Column], sizes: Sequence[int]) -> str:
    parts = [
        cell.rjust(size) if column.numeric else cell.ljust(size)
        for cell, column, size in zip(cells, columns, sizes, strict=True)
    ]
    return "  ".join(parts).rstrip()


def as_csv(rows: Sequence[Mapping[str, object]], columns: Sequence[Column]) -> str:
    """Return the rows as comma separated text, headings included."""
    if not columns:
        raise Invalid("columns", 0, "a table needs a column in it")
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow([column.title for column in columns])
    for row in rows:
        writer.writerow([column.render(row.get(column.key)) for column in columns])
    return buffer.getvalue()


def totals(rows: Sequence[Mapping[str, object]], key: str) -> float:
    """Return the sum of one numeric column, skipping rows without it."""
    running = 0.0
    for row in rows:
        value = row.get(key)
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, int | float):
            running += float(value)
    return round(running, 4)
