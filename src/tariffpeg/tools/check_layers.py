"""The layers only import downwards.

The rule that earns its place is that nothing below the command line imports the
command line, and nothing outside the store imports sqlite. Those two are what
keep the whole pipeline runnable from a recorded bundle with no database and no
terminal, which is how a disputed case file gets answered.

The table below is the whole architecture, written where a check can read it.
"""

from __future__ import annotations

import sys

from tariffpeg.tools.walk import PACKAGE, report, source_files

NAME = "check_layers"

BASE = ("",)
"""The layer holding the errors, the identifiers and the clock."""

ALLOWED: dict[str, tuple[str, ...]] = {
    "": BASE,
    "model": (*BASE, "model"),
    "fetch": (*BASE, "model", "fetch"),
    "parse": (*BASE, "model", "parse"),
    "normalise": (*BASE, "model", "parse", "normalise"),
    "dedupe": (*BASE, "model", "dedupe"),
    "claims": (*BASE, "model", "claims"),
    "sample": (*BASE, "model", "dedupe", "sample"),
    "store": (*BASE, "model", "store"),
    "harvest": (*BASE, "model", "fetch", "parse", "normalise", "sample", "store", "harvest"),
    "triage": (*BASE, "model", "claims", "dedupe", "sample", "triage"),
    "report": (*BASE, "model", "claims", "dedupe", "sample", "triage", "report"),
    "cli": (),
    "tools": (),
}
"""Which layer may import which. An empty tuple means anything."""

FREE_MODULES = frozenset({f"{PACKAGE}.service"})
"""The modules whose whole job is to join the layers up."""

SQLITE_LAYERS = frozenset({"store", "tools"})
"""Where the database module may be imported."""


def layer_of(module: str) -> str:
    """Return the layer a dotted module name sits in."""
    parts = module.split(".")
    return parts[1] if len(parts) > 2 else ""


def problems() -> list[str]:
    """Return every import that goes the wrong way."""
    found: list[str] = []
    for source in source_files():
        allowed = ALLOWED.get(source.layer)
        for imported in source.imports():
            if imported == "sqlite3" and source.layer not in SQLITE_LAYERS:
                found.append(f"{source.where} imports sqlite3, which only the store may do")
            if not imported.startswith(f"{PACKAGE}."):
                continue
            if source.module in FREE_MODULES:
                continue
            wanted = layer_of(imported)
            if wanted == "cli" and source.layer not in ("cli", "tools"):
                found.append(f"{source.where} imports the command line")
                continue
            if allowed and wanted not in allowed:
                found.append(
                    f"{source.where} is in {source.layer or 'the base layer'}"
                    f" and imports {imported}, which is in {wanted or 'the base layer'}"
                )
    return found


def main() -> int:
    """Run the check and return an exit code."""
    return report(NAME, problems())


if __name__ == "__main__":
    sys.exit(main())
