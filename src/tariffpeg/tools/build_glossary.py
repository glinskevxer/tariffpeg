"""Write the glossary out of the vocabularies the code actually uses.

Everybody who joins this unit asks what a particular is, what a voice is and why
a stay month is not a date. The answers are in the code, so the glossary is
written from the code rather than kept beside it going out of date.
"""

from __future__ import annotations

import sys
from enum import StrEnum

from tariffpeg.claims.rules import Persistence, Polarity
from tariffpeg.dedupe.syndication import Verdict
from tariffpeg.model.channel import SyndicationClass
from tariffpeg.model.licence import LicenceStatus
from tariffpeg.model.outcome import Disposition
from tariffpeg.model.particulars import SPECS
from tariffpeg.model.period import Season
from tariffpeg.parse.drift import DriftState
from tariffpeg.tools.document import render, run, table

NAME = "build_glossary"
DOCUMENT = "glossary.md"

VOCABULARIES: tuple[tuple[str, type[StrEnum], str], ...] = (
    ("Licence status", LicenceStatus, "Where a licence sits in its life."),
    ("Season", Season, "Which part of the trading year a stay falls in."),
    ("Syndication class", SyndicationClass, "Where a channel gets its reviews."),
    ("Polarity", Polarity, "Which way a matched phrase points."),
    ("Persistence", Persistence, "Whether a finding is a feature or an incident."),
    ("Syndication verdict", Verdict, "What the comparison made of a pair of reviews."),
    ("Profile drift", DriftState, "What the readings for a profile add up to."),
    ("Disposition", Disposition, "What happens to a licence."),
)
"""The vocabularies worth writing down, in the order they are met."""


def body() -> list[str]:
    """Return the lines of the glossary."""
    lines = [
        "## Particulars",
        "",
        "The claims an operator registers on a licence. A review can only"
        " contradict something on this list.",
        "",
    ]
    rows = [
        [f"`{spec.key}`", str(spec.kind), spec.label, str(spec.tolerance or "")] for spec in SPECS
    ]
    lines.extend(table(["particular", "measured as", "what it means", "tolerance"], rows))
    lines.append("")
    for title, vocabulary, sentence in VOCABULARIES:
        lines.append(f"## {title}")
        lines.append("")
        lines.append(sentence)
        lines.append("")
        lines.extend(table(["value"], [[f"`{member}`"] for member in vocabulary]))
        lines.append("")
    return lines


def text() -> str:
    """Return the whole glossary."""
    return render(NAME, "Glossary", body())


def main() -> int:
    """Write the document, or check it, and return an exit code."""
    return run(NAME, DOCUMENT, text())


if __name__ == "__main__":
    sys.exit(main())
