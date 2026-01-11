"""One command that runs every gate, so a release is a single answer.

Somebody has to be able to say yes or no before a version goes out. This is
that, and it fails loudly rather than skipping a gate it cannot run: a gate that
quietly passes because its tool could not be imported is worse than no gate.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from dataclasses import dataclass

from tariffpeg import __version__
from tariffpeg.tools.walk import repo_root, report, source_root

NAME = "release_check"

GENERATED = (
    "schema_dump",
    "build_architecture",
    "build_commands",
    "build_glossary",
    "build_operations",
    "build_rules",
)
"""The documents that have to be up to date before a release."""


@dataclass(frozen=True, slots=True)
class Gate:
    """One thing that has to pass."""

    name: str
    run: Callable[[], list[str]]


def _checks() -> list[str]:
    return sorted(path.stem for path in (source_root() / "tools").glob("check_*.py"))


def _run_tool(module: str, argv: list[str] | None = None) -> list[str]:
    try:
        loaded = importlib.import_module(f"tariffpeg.tools.{module}")
    except ImportError as err:
        return [f"{module} could not be imported: {err}"]
    saved = sys.argv
    sys.argv = [module, *(argv or [])]
    try:
        code = loaded.main()
    finally:
        sys.argv = saved
    return [] if code == 0 else [f"{module} did not pass"]


def version_agrees() -> list[str]:
    """Return whether the version in the code matches the packaging."""
    text = (repo_root() / "pyproject.toml").read_text(encoding="utf-8")
    wanted = f'version = "{__version__}"'
    if wanted not in text:
        return [f"pyproject.toml does not say {wanted}"]
    return []


def changelog_mentions_this_version() -> list[str]:
    """Return whether the changelog has an entry for the version going out."""
    target = repo_root() / "CHANGELOG.md"
    if not target.exists():
        return ["there is no CHANGELOG.md"]
    if __version__ not in target.read_text(encoding="utf-8"):
        return [f"CHANGELOG.md says nothing about {__version__}"]
    return []


def readme_points_at_the_documents() -> list[str]:
    """Return whether the readme links every generated document."""
    target = repo_root() / "README.md"
    if not target.exists():
        return ["there is no README.md"]
    text = target.read_text(encoding="utf-8")
    missing = [name for name in GENERATED if _document_of(name) not in text]
    return [f"README.md does not point at {name}" for name in missing]


def _document_of(generator: str) -> str:
    return "schema.md" if generator == "schema_dump" else f"{generator.removeprefix('build_')}.md"


def gates() -> list[Gate]:
    """Return every gate, in the order they run."""
    found = [Gate("version", version_agrees), Gate("changelog", changelog_mentions_this_version)]
    found.append(Gate("readme", readme_points_at_the_documents))
    for check in _checks():
        found.append(Gate(check, lambda check=check: _run_tool(check)))  # type: ignore[misc]
    for generator in GENERATED:
        found.append(
            Gate(generator, lambda generator=generator: _run_tool(generator, ["--check"]))  # type: ignore[misc]
        )
    found.append(Gate("smoke", lambda: _run_tool("smoke", ["--quiet"])))
    return found


def problems(verbose: bool = False) -> list[str]:
    """Run every gate and return what failed."""
    found: list[str] = []
    for gate in gates():
        outcome = gate.run()
        if verbose:
            print(f"{NAME}: {gate.name} {'failed' if outcome else 'passed'}")
        found.extend(outcome)
    return found


def main() -> int:
    """Run every gate and return an exit code."""
    verbose = "--verbose" in sys.argv[1:]
    found = problems(verbose)
    print(f"{NAME}: {len(gates())} gates")
    return report(NAME, found)


if __name__ == "__main__":
    sys.exit(main())
