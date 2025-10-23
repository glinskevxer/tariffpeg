"""Refusals are raised with the right pieces and read as sentences.

The messages here end up in front of somebody who is not a programmer, in a
terminal at eight in the morning, and they are the only thing that says what to
do next. So the reason a refusal carries is a lowercase clause with no full stop
on it, because the caller wraps it in a sentence of its own.

The argument counts are checked because a refusal built with the wrong number of
pieces raises a TypeError from inside the error path, which is the one place
nothing is watching.
"""

from __future__ import annotations

import ast
import sys

from tariffpeg.tools.walk import report, source_files

NAME = "check_errors"

WANTED = {
    "NotFound": 2,
    "AlreadyExists": 2,
    "Invalid": 3,
    "Conflict": 2,
    "FetchFailed": 2,
    "Refused": 2,
}
"""How many pieces each refusal is built from."""

REASON_AT = {"Invalid": 2, "Conflict": 1, "FetchFailed": 1, "Refused": 1}
"""Which argument carries the clause a person reads."""

NEVER = frozenset({"Exception", "BaseException", "NotImplementedError", "RuntimeError"})
"""Nothing in this package raises these on purpose."""


def _name_of(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _reason_problems(where: str, kind: str, call: ast.Call) -> list[str]:
    at = REASON_AT.get(kind)
    if at is None or len(call.args) <= at:
        return []
    reason = call.args[at]
    if not isinstance(reason, ast.Constant) or not isinstance(reason.value, str):
        return []
    text = reason.value
    found: list[str] = []
    if text.endswith("."):
        found.append(f"{where}:{call.lineno} the reason on {kind} ends with a full stop")
    if text[:1].isupper():
        found.append(f"{where}:{call.lineno} the reason on {kind} starts with a capital")
    if not text.strip():
        found.append(f"{where}:{call.lineno} the reason on {kind} is blank")
    return found


def problems() -> list[str]:
    """Return every refusal raised with the wrong pieces or the wrong wording."""
    found: list[str] = []
    for source in source_files():
        for node in ast.walk(source.tree):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            call = node.exc if isinstance(node.exc, ast.Call) else None
            kind = _name_of(call.func) if call else _name_of(node.exc)
            if kind in NEVER:
                found.append(f"{source.where}:{node.lineno} raises {kind}")
                continue
            if call is None or kind not in WANTED:
                continue
            if len(call.args) != WANTED[kind]:
                found.append(
                    f"{source.where}:{node.lineno} builds {kind} from"
                    f" {len(call.args)} pieces, not {WANTED[kind]}"
                )
                continue
            found.extend(_reason_problems(source.where, kind, call))
    return found


def main() -> int:
    """Run the check and return an exit code."""
    return report(NAME, problems())


if __name__ == "__main__":
    sys.exit(main())
