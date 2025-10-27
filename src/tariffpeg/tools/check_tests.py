"""Every module has a test module, and every public name is named somewhere in it.

The second half is the one that catches things. A module can have a test file
beside it that exercises two of its nine functions, and nothing says so. Naming
a function somewhere in the suite is a low bar, but a function nobody has ever
called does not clear it.

Command line functions are named by their command rather than by their python
name, because that is how they are reached. A command nobody has typed in a test
is a command nobody has run.
"""

from __future__ import annotations

import ast
import sys

from tariffpeg.tools.walk import PACKAGE, SourceFile, package_files, report, suite_files

NAME = "check_tests"

NO_TEST_WANTED = frozenset({f"{PACKAGE}", f"{PACKAGE}.cli.main"})
"""The package init carries only a version, and the entry point is exercised
through every command rather than on its own."""

CLICK_DECORATORS = ("command", "group")
"""The decorators that turn a function into something typed rather than called."""


def expected_test(module: str) -> str:
    """Return the test module a package module is tested by."""
    parts = module.split(".")[1:]
    parts[-1] = f"test_{parts[-1]}"
    return "tests." + ".".join(parts)


def command_name(node: ast.FunctionDef) -> str | None:
    """Return the command a function is reached by, or nothing if it is not one."""
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        func = decorator.func
        attr = func.attr if isinstance(func, ast.Attribute) else ""
        if attr not in CLICK_DECORATORS:
            continue
        for keyword in decorator.keywords:
            if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                return str(keyword.value.value)
        return node.name.removesuffix("_command").removesuffix("_group")
    return None


def wanted_names(source: SourceFile) -> list[str]:
    """Return the names the suite has to mention for one file."""
    names: list[str] = []
    for name, node in source.named():
        if "." in name or name.startswith("_"):
            continue
        if isinstance(node, ast.FunctionDef):
            command = command_name(node)
            if command is not None:
                names.append(command)
                continue
        names.append(name)
    return names


def problems() -> list[str]:
    """Return every module with no test module, and every name nobody names."""
    suite = suite_files()
    modules = {found.module for found in suite}
    everything = "\n".join(found.text for found in suite)
    found: list[str] = []
    for source in package_files():
        if source.module in NO_TEST_WANTED or source.path.name == "__init__.py":
            continue
        wanted = expected_test(source.module)
        if wanted not in modules:
            found.append(f"{source.where} has no {wanted.replace('.', '/')}.py")
            continue
        for name in wanted_names(source):
            if name not in everything:
                found.append(f"{source.where} defines {name}, which the suite never names")
    return found


def main() -> int:
    """Run the check and return an exit code."""
    return report(NAME, problems())


if __name__ == "__main__":
    sys.exit(main())
