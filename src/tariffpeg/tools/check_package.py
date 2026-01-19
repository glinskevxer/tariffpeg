"""The packaging says the same thing twice and both copies agree.

Two failures this catches. A dependency added to the project file and not pinned
in the constraints file, which makes a rebuild in a year resolve to something
else. And a third party import in the package that nothing declares, which works
on the machine it was written on and nowhere else.
"""

from __future__ import annotations

import re
import sys
import tomllib

from tariffpeg.tools.walk import PACKAGE, package_files, repo_root, report

NAME = "check_package"

STANDARD_LIBRARY = frozenset(sys.stdlib_module_names)
"""What comes with python and needs no declaring."""

REQUIREMENT = re.compile(r"^([A-Za-z0-9_.-]+)")


def _named(requirement: str) -> str:
    found = REQUIREMENT.match(requirement.strip())
    return found.group(1).lower().replace("_", "-") if found else ""


def project() -> dict[str, object]:
    """Return the project table out of the packaging file."""
    text = (repo_root() / "pyproject.toml").read_text(encoding="utf-8")
    loaded = tomllib.loads(text)
    return dict(loaded.get("project", {}))


def constrained() -> set[str]:
    """Return the names pinned in the constraints file."""
    target = repo_root() / "constraints.txt"
    if not target.exists():
        return set()
    names: set[str] = set()
    for line in target.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            names.add(_named(line))
    return names


def declared() -> set[str]:
    """Return every dependency the project file names, dev ones included."""
    table = project()
    listed: list[str] = []
    direct = table.get("dependencies")
    if isinstance(direct, list):
        listed.extend(str(item) for item in direct)
    extras = table.get("optional-dependencies")
    if isinstance(extras, dict):
        for group in extras.values():
            if isinstance(group, list):
                listed.extend(str(item) for item in group)
    return {_named(item) for item in listed}


def imported() -> set[str]:
    """Return every third party package the code imports."""
    found: set[str] = set()
    for source in package_files():
        for name in source.imports():
            root = name.split(".")[0]
            if root in STANDARD_LIBRARY or root == PACKAGE:
                continue
            found.add(root.lower().replace("_", "-"))
    return found


def problems() -> list[str]:
    """Return everything the packaging says twice and disagrees about."""
    found: list[str] = []
    pins = constrained()
    if not pins:
        found.append("there is no constraints.txt")
        return found
    for name in sorted(declared() - pins):
        found.append(f"{name} is a dependency but is not pinned in constraints.txt")
    for name in sorted(imported() - declared()):
        found.append(f"the package imports {name}, which nothing declares")
    table = project()
    if not str(table.get("requires-python", "")).startswith(">="):
        found.append("the project file does not say which python versions it supports")
    if "scripts" not in table:
        found.append("the project file declares no console script")
    return found


def main() -> int:
    """Run the check and return an exit code."""
    return report(NAME, problems())


if __name__ == "__main__":
    sys.exit(main())
