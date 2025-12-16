"""Writing a generated document, and saying when it has gone stale.

Every generator here writes one file under ``docs`` and every one of them can be
run with ``--check`` instead, which writes nothing and exits non zero if the file
on disk is not what the code would produce. That is the version that runs in the
pipeline, so a document that drifts from the code it describes stops a build
rather than misleading somebody.
"""

from __future__ import annotations

import sys
from pathlib import Path

from tariffpeg.tools.walk import repo_root

DOCS = "docs"
"""Where the generated documents live."""

BANNER = "<!-- Written by {generator}. Do not edit it here. -->"
"""What every generated document says at the top of itself."""


def document_path(name: str) -> Path:
    """Return where a generated document lives."""
    return repo_root() / DOCS / name


def render(generator: str, title: str, body: list[str]) -> str:
    """Return a whole document, banner and all."""
    lines = [f"# {title}", "", BANNER.format(generator=generator), "", *body]
    return "\n".join(lines).rstrip() + "\n"


def write(name: str, text: str) -> Path:
    """Write a document and return where it went."""
    target = document_path(name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")
    return target


def stale(name: str, text: str) -> str:
    """Return what is wrong with the document on disk, or an empty string."""
    target = document_path(name)
    if not target.exists():
        return f"{name} has never been written"
    held = target.read_text(encoding="utf-8")
    if held != text:
        return f"{name} is not what the code would write"
    return ""


def run(generator: str, name: str, text: str, argv: list[str] | None = None) -> int:
    """Write the document, or check it, and return an exit code."""
    args = sys.argv[1:] if argv is None else argv
    if "--check" in args:
        problem = stale(name, text)
        if problem:
            print(f"{generator}: {problem}")
            return 1
        print(f"{generator}: {name} is up to date")
        return 0
    target = write(name, text)
    print(f"{generator}: wrote {target}")
    return 0


def table(headings: list[str], rows: list[list[str]]) -> list[str]:
    """Return a markdown table as lines."""
    lines = ["| " + " | ".join(headings) + " |"]
    lines.append("| " + " | ".join("---" for _ in headings) + " |")
    for row in rows:
        lines.append("| " + " | ".join(cell.replace("|", chr(92) + "|") for cell in row) + " |")
    return lines
