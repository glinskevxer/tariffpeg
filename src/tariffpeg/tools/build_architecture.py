"""Write the architecture document out of the layer table and the tree.

The table in the layer check is the architecture. This prints it, together with
the modules that are actually in each layer, so that a drawing on somebody wall
is never the only description of the shape of this thing.
"""

from __future__ import annotations

import sys

from tariffpeg.tools.check_layers import ALLOWED, FREE_MODULES
from tariffpeg.tools.document import render, run, table
from tariffpeg.tools.walk import package_files

NAME = "build_architecture"
DOCUMENT = "architecture.md"

SENTENCES = {
    "": "The errors, the identifiers, the clock and the settings.",
    "model": "The records the store holds and the rules about what they may contain.",
    "fetch": "Talking to a channel, or replaying what a channel said.",
    "parse": "Turning a served page into the reviews on it.",
    "normalise": "Turning what came off a page into something the store will accept.",
    "dedupe": "Working out when two reviews are the same review.",
    "claims": "Setting what a guest said against what the operator signed for.",
    "sample": "How many reviews a licence has to be sampled with.",
    "store": "The one SQLite file, and everything that reads or writes it.",
    "harvest": "Planning a run and walking it.",
    "triage": "Weighing the evidence and deciding what happens.",
    "report": "The case file an inspector is handed.",
    "cli": "The commands the unit types.",
    "tools": "The checks and the generated documents. Nothing imports these.",
}
"""What each layer is for, in one line."""


def modules_by_layer() -> dict[str, list[str]]:
    """Return the modules in each layer, by dotted name."""
    found: dict[str, list[str]] = {}
    for source in package_files():
        if source.path.name == "__init__.py":
            continue
        found.setdefault(source.layer, []).append(source.module)
    return found


def body() -> list[str]:
    """Return the lines of the architecture document."""
    held = modules_by_layer()
    lines = [
        "A layer may import the layers listed against it and nothing else."
        " The check that enforces this is `check_layers`.",
        "",
    ]
    rows = [
        [
            layer or "(base)",
            SENTENCES.get(layer, ""),
            ", ".join(name or "(base)" for name in allowed) if allowed else "anything",
        ]
        for layer, allowed in ALLOWED.items()
    ]
    lines.extend(table(["layer", "what it is for", "may import"], rows))
    lines.append("")
    lines.append(
        "These modules join the layers up and may import anything: "
        + ", ".join(f"`{name}`" for name in sorted(FREE_MODULES))
        + "."
    )
    lines.append("")
    lines.append("## What is in each layer")
    lines.append("")
    for layer in ALLOWED:
        names = sorted(held.get(layer, []))
        if not names:
            continue
        lines.append(f"### {layer or '(base)'}")
        lines.append("")
        lines.extend(f"- `{name}`" for name in names)
        lines.append("")
    return lines


def text() -> str:
    """Return the whole architecture document."""
    return render(NAME, "Architecture", body())


def main() -> int:
    """Write the document, or check it, and return an exit code."""
    return run(NAME, DOCUMENT, text())


if __name__ == "__main__":
    sys.exit(main())
