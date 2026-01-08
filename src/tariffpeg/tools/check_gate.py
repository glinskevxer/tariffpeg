"""The three places that list the tools all list the same tools.

There are three: the script somebody runs before they push, the pipeline that
runs on the branch, and the release check. A tool added to one and forgotten in
the other two is a tool that only runs where nobody is looking, which is the
same as not having written it.

The list of tools is read off the directory rather than kept here, so adding one
and forgetting it anywhere is caught by this on the next run.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from tariffpeg.tools.walk import repo_root, report, source_root

NAME = "check_gate"

SCRIPT = "check.sh"
WORKFLOW = ".github/workflows/ci.yml"

INVOCATION = re.compile(r"tariffpeg\.tools\.(\w+)")


def tools_on_disk() -> tuple[set[str], set[str]]:
    """Return the checks and the generators that exist, by module name."""
    directory = source_root() / "tools"
    checks = {path.stem for path in directory.glob("check_*.py")}
    builders = {path.stem for path in directory.glob("build_*.py")}
    builders.add("schema_dump")
    return checks, builders


def named_in(path: Path) -> set[str]:
    """Return the tools a file invokes."""
    if not path.exists():
        return set()
    return set(INVOCATION.findall(path.read_text(encoding="utf-8")))


def problems() -> list[str]:
    """Return every tool that is missing from somewhere it should be."""
    checks, builders = tools_on_disk()
    wanted = checks | builders
    found: list[str] = []
    script = repo_root() / SCRIPT
    if not script.exists():
        found.append(f"there is no {SCRIPT}")
    workflow = repo_root() / WORKFLOW
    if not workflow.exists():
        found.append(f"there is no {WORKFLOW}")
        return found
    in_workflow = named_in(workflow)
    for tool in sorted(wanted - in_workflow):
        found.append(f"{tool} is not run by {WORKFLOW}")
    for tool in sorted(in_workflow - wanted - {"smoke", "release_check"}):
        found.append(f"{WORKFLOW} runs {tool}, which is not a tool in the tree")
    if "smoke" not in in_workflow:
        found.append(f"{WORKFLOW} never runs the smoke run")
    text = script.read_text(encoding="utf-8") if script.exists() else ""
    for wildcard in ("check_*.py", "build_*.py"):
        if wildcard not in text:
            found.append(f"{SCRIPT} does not pick up {wildcard} by wildcard")
    return found


def main() -> int:
    """Run the check and return an exit code."""
    return report(NAME, problems())


if __name__ == "__main__":
    sys.exit(main())
