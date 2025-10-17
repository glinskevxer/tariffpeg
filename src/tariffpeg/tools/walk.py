"""Finding the files the checks read, and parsing them once.

Every check in this directory imports :func:`source_files` and
:func:`suite_files` at module level. That is deliberate. A check that reaches
through this module cannot be pointed at anything else, and a check that has
only ever run against a clean tree is a check whose failure branch has never
executed.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

PACKAGE = "tariffpeg"
"""The package the checks read."""


@cache
def repo_root() -> Path:
    """Return the root of the working tree."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("this file is not inside the repository any more")


def source_root() -> Path:
    """Return the directory the package lives in."""
    return repo_root() / "src" / PACKAGE


def suite_root() -> Path:
    """Return the directory the tests live in."""
    return repo_root() / "tests"


@dataclass(frozen=True, slots=True)
class SourceFile:
    """One file, parsed once and asked about many times."""

    path: Path
    text: str
    tree: ast.Module = field(compare=False, repr=False)

    @property
    def module(self) -> str:
        """Return the dotted module name.

        A file under ``src`` is named as the package sees it. A file under
        ``tests`` is named as the suite sees it, which is what lets one check
        line the two lists up against each other.
        """
        relative = self.path.relative_to(repo_root())
        parts = list(relative.with_suffix("").parts)
        if parts and parts[0] == "src":
            parts.pop(0)
        if parts and parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts)

    @property
    def layer(self) -> str:
        """Return the subpackage this file sits in, or nothing for a top level one.

        This is read off the directory rather than off the dotted name, because
        ``tariffpeg/errors.py`` and ``tariffpeg/errors/__init__.py`` would
        otherwise read the same and only one of them is in a subpackage.
        """
        parent = self.path.parent
        return "" if parent == source_root() else parent.name

    @property
    def where(self) -> str:
        """Return the path as the checks print it."""
        return str(self.path.relative_to(repo_root())).replace("\\", "/")

    def lines(self) -> list[str]:
        """Return the file split into lines."""
        return self.text.splitlines()

    def functions(self) -> list[ast.FunctionDef]:
        """Return every function defined anywhere in the file."""
        return [node for node in ast.walk(self.tree) if isinstance(node, ast.FunctionDef)]

    def classes(self) -> list[ast.ClassDef]:
        """Return every class defined in the file."""
        return [node for node in ast.walk(self.tree) if isinstance(node, ast.ClassDef)]

    def named(self) -> list[tuple[str, ast.FunctionDef | ast.ClassDef]]:
        """Return the functions and classes a caller elsewhere can reach.

        Nested functions are left out. A closure inside a function is a private
        helper however it is spelled, and nothing outside can call it.
        """
        found: list[tuple[str, ast.FunctionDef | ast.ClassDef]] = []
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef | ast.ClassDef):
                found.append((node.name, node))
            if isinstance(node, ast.ClassDef):
                found.extend(
                    (f"{node.name}.{inner.name}", inner)
                    for inner in node.body
                    if isinstance(inner, ast.FunctionDef | ast.ClassDef)
                )
        return found

    def top_level(self) -> list[ast.stmt]:
        """Return the statements at the top of the file."""
        return list(self.tree.body)

    def imports(self) -> list[str]:
        """Return every module this file imports, by dotted name."""
        found: list[str] = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                found.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.append(node.module)
        return found

    def constant(self, name: str) -> ast.expr | None:
        """Return the value assigned to a top level name, if there is one."""
        for node in self.tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == name:
                        return node.value
            if (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == name
                and node.value is not None
            ):
                return node.value
        return None


def read(path: Path) -> SourceFile:
    """Read and parse one file."""
    text = path.read_text(encoding="utf-8")
    return SourceFile(path, text, ast.parse(text, filename=str(path)))


def source_files() -> list[SourceFile]:
    """Return every file in the package, in path order."""
    return [read(path) for path in sorted(source_root().rglob("*.py"))]


def suite_files() -> list[SourceFile]:
    """Return every file in the suite, in path order."""
    return [read(path) for path in sorted(suite_root().rglob("*.py"))]


def package_files() -> list[SourceFile]:
    """Return the package files that are not tools."""
    return [found for found in source_files() if found.layer != "tools"]


def report(name: str, problems: list[str]) -> int:
    """Print what a check found and return the exit code it should use."""
    if not problems:
        print(f"{name}: clean")
        return 0
    for problem in problems:
        print(f"{name}: {problem}")
    print(f"{name}: {len(problems)} problems")
    return 1
