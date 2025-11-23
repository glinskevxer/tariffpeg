"""The migrations are numbered, named and frozen.

A migration that has run somewhere cannot be edited. Editing one produces a
store whose bookkeeping says it ran a statement it did not run, and the drift
check in the store will say so months later on somebody else's machine. This
catches it here instead, by keeping the digests in a file beside the code.

Write the file with ``--write`` when a migration is added on purpose. There is
no way to write it by accident, which is the point.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from tariffpeg.store.migrations import MIGRATIONS
from tariffpeg.tools.walk import repo_root, report

NAME = "check_migrations"

LOCK = "migrations.lock"
"""Where the digests are frozen."""

SLUG = re.compile(r"^[a-z][a-z0-9-]*$")


def lock_path() -> Path:
    """Return where the lock file lives."""
    return repo_root() / LOCK


def render_lock() -> str:
    """Return the lock file the migrations in the code would produce."""
    lines = [f"{m.number:03d} {m.name} {m.digest}" for m in MIGRATIONS]
    return "\n".join(lines) + "\n"


def read_lock() -> dict[int, tuple[str, str]]:
    """Return what the lock file says, by migration number."""
    target = lock_path()
    if not target.exists():
        return {}
    found: dict[int, tuple[str, str]] = {}
    for line in target.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 3:
            found[int(parts[0])] = (parts[1], parts[2])
    return found


def problems() -> list[str]:
    """Return everything wrong with the migrations or the lock file."""
    found: list[str] = []
    numbers = [migration.number for migration in MIGRATIONS]
    if numbers != list(range(1, len(numbers) + 1)):
        found.append(f"the migrations are numbered {numbers}, not one upwards with no gaps")
    seen: set[str] = set()
    for migration in MIGRATIONS:
        if not SLUG.match(migration.name):
            found.append(f"migration {migration.number} is named {migration.name!r}, not a slug")
        if migration.name in seen:
            found.append(f"migration {migration.number} reuses the name {migration.name!r}")
        seen.add(migration.name)
        if not migration.statements:
            found.append(f"migration {migration.number} runs nothing")
        for statement in migration.statements:
            if statement.strip().endswith(";"):
                found.append(f"migration {migration.number} has a statement ending in a semicolon")
    locked = read_lock()
    if not locked:
        found.append(f"there is no {LOCK}, run this check with --write to make one")
        return found
    for migration in MIGRATIONS:
        held = locked.get(migration.number)
        if held is None:
            found.append(f"migration {migration.number} is not in {LOCK}")
        elif held != (migration.name, migration.digest):
            found.append(f"migration {migration.number} has changed since {LOCK} was written")
    for number in sorted(set(locked) - set(numbers)):
        found.append(f"{LOCK} carries migration {number}, which the code does not")
    return found


def write() -> Path:
    """Write the lock file and return where it went."""
    target = lock_path()
    target.write_text(render_lock(), encoding="utf-8", newline="\n")
    return target


def main() -> int:
    """Run the check, or write the lock file, and return an exit code."""
    if "--write" in sys.argv[1:]:
        print(f"{NAME}: wrote {write()}")
        return 0
    return report(NAME, problems())


if __name__ == "__main__":
    sys.exit(main())
