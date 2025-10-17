"""Building a source file out of text, so a check can be pointed at a defect.

Every check here comes back clean against the real tree, which means the branch
that writes the message never runs. These fixtures build a file that is not on
disk and hand it to the check in place of the real ones.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from types import ModuleType

import pytest

from tariffpeg.tools.walk import SourceFile, repo_root


def make_source(relative: str, text: str) -> SourceFile:
    """Return a parsed file that is not on disk."""
    path = repo_root() / "src" / relative
    return SourceFile(path, text, ast.parse(text, filename=str(path)))


def make_test(relative: str, text: str) -> SourceFile:
    """Return a parsed test file that is not on disk."""
    path = repo_root() / relative
    return SourceFile(path, text, ast.parse(text, filename=str(path)))


Planter = Callable[[ModuleType, str, list[SourceFile]], None]


@pytest.fixture
def plant(monkeypatch: pytest.MonkeyPatch) -> Planter:
    """Point a check at files that are not on disk."""

    def apply(module: ModuleType, name: str, files: list[SourceFile]) -> None:
        monkeypatch.setattr(module, name, lambda: files)

    return apply
