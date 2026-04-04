"""Reading the register extract the licensing system sends every quarter.

It arrives as a comma separated file with a header row and it is never quite
right. A row with a bad date in it should not stop the other four hundred, so
nothing here raises: every row comes back either as a licence or as a line
saying which row and what was wrong with it.

The particular columns are whatever the header says they are, which is how a new
particular gets imported without a release.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
from collections.abc import Mapping
from dataclasses import dataclass, field

from tariffpeg.errors import Invalid
from tariffpeg.model.licence import Licence, LicenceStatus
from tariffpeg.model.particulars import BY_KEY, parse_value

REQUIRED_COLUMNS = (
    "serial",
    "trading_name",
    "operator_name",
    "locality",
    "period_start",
    "period_end",
)
"""The columns the extract has to carry."""

OPTIONAL_COLUMNS = ("closed_months", "status", "operator_ref")
"""The columns it may carry."""


@dataclass(slots=True)
class Reading:
    """What one extract gave up."""

    licences: list[Licence] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Return whether every row read."""
        return not self.problems

    def summary(self) -> str:
        """Return the line the command line prints."""
        return f"{len(self.licences)} rows read, {len(self.problems)} refused"


def _months(written: str) -> frozenset[int]:
    return frozenset(int(part) for part in written.split(",") if part.strip())


def _particulars(row: Mapping[str, str]) -> dict[str, bool | int]:
    found: dict[str, bool | int] = {}
    for column, written in row.items():
        if column in BY_KEY and written.strip():
            found[column] = parse_value(column, written)
    return found


def _licence(row: Mapping[str, str]) -> Licence:
    return Licence(
        serial=int(row["serial"]),
        trading_name=row["trading_name"].strip(),
        operator_name=row["operator_name"].strip(),
        locality=row["locality"].strip(),
        period_start=dt.date.fromisoformat(row["period_start"].strip()),
        period_end=dt.date.fromisoformat(row["period_end"].strip()),
        particulars=_particulars(row),
        closed_months=_months(row.get("closed_months", "")),
        status=LicenceStatus(row.get("status", "").strip() or "active"),
        operator_ref=row.get("operator_ref", "").strip(),
    )


def read_text(text: str) -> Reading:
    """Read a register extract, keeping every row that reads."""
    reading = Reading()
    rows = csv.DictReader(io.StringIO(text))
    if rows.fieldnames is None:
        reading.problems.append("the extract has no header row")
        return reading
    missing = [name for name in REQUIRED_COLUMNS if name not in rows.fieldnames]
    if missing:
        reading.problems.append(f"the extract has no {missing[0]} column")
        return reading
    unknown = [
        name
        for name in rows.fieldnames
        if name not in REQUIRED_COLUMNS and name not in OPTIONAL_COLUMNS and name not in BY_KEY
    ]
    if unknown:
        reading.problems.append(f"the extract carries a column nobody reads: {unknown[0]}")
        return reading
    for number, row in enumerate(rows, start=2):
        try:
            reading.licences.append(_licence(row))
        except (Invalid, ValueError, KeyError) as err:
            reason = err.reason if isinstance(err, Invalid) else str(err)
            reading.problems.append(f"row {number}: {reason}")
    return reading
