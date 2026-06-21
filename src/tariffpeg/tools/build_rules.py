"""Write the rule pack out as a document an inspector can read in a hearing.

The pack is data and this is that data with the columns headed. It is the thing
that gets printed and put in the bundle when an operator asks on what basis a
sentence in a review was treated as saying their lift does not exist.
"""

from __future__ import annotations

import sys

from tariffpeg.claims.pack import (
    ADDED_IN_TWO,
    METRES_A_MILE,
    METRES_A_MINUTE_WALKING,
    PACK,
    published_versions,
)
from tariffpeg.model.particulars import spec_for
from tariffpeg.tools.document import render, run, table

NAME = "build_rules"
DOCUMENT = "rules.md"


def body() -> list[str]:
    """Return the lines of the rules document."""
    lines = [
        f"Pack version {PACK.version}, {len(PACK.rules)} rules.",
        "",
        "A structural rule describes a feature of the premises. A transient one"
        " describes something that was true for a stay. The two decay at"
        " different rates and the second needs company before it is worth a"
        " visit.",
        "",
        f"A walk in minutes is read as {METRES_A_MINUTE_WALKING} metres a minute,"
        f" and a distance in miles as {METRES_A_MILE} metres a mile.",
        "",
        "Published packs: "
        + ", ".join(str(number) for number in published_versions())
        + ". An older pack stays readable so that a case file which cited it can"
        " still be answered in its own terms.",
        "",
        "Added since pack one: " + ", ".join(f"`{rule.rule_id}`" for rule in ADDED_IN_TWO) + ".",
        "",
    ]
    for claim_key in PACK.claim_keys():
        spec = spec_for(claim_key)
        lines.append(f"## {claim_key}")
        lines.append("")
        lines.append(f"{spec.label.capitalize()}. Measured as a {spec.kind}.")
        if spec.tolerance:
            edge = "over only" if spec.upper_only else "either way"
            lines.append(f"Tolerance {spec.tolerance}, {edge}.")
        lines.append("")
        rows = [
            [
                f"`{rule.rule_id}`",
                f"`{rule.pattern}`",
                str(rule.polarity),
                str(rule.persistence),
                str(rule.strength),
            ]
            for rule in PACK.for_claim(claim_key)
        ]
        lines.extend(table(["rule", "pattern", "says", "kind", "weight"], rows))
        lines.append("")
        for rule in PACK.for_claim(claim_key):
            if rule.note:
                lines.append(f"`{rule.rule_id}`: {rule.note}.")
        if any(rule.note for rule in PACK.for_claim(claim_key)):
            lines.append("")
    return lines


def text() -> str:
    """Return the whole rules document."""
    return render(NAME, "Rule pack", body())


def main() -> int:
    """Write the document, or check it, and return an exit code."""
    return run(NAME, DOCUMENT, text())


if __name__ == "__main__":
    sys.exit(main())
