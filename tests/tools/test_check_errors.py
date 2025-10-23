"""The error path is the one place nothing is watching."""

from __future__ import annotations

from tariffpeg.tools import check_errors
from tariffpeg.tools.walk import SourceFile
from tests.tools.conftest import Planter, make_source


def source(body: str) -> SourceFile:
    return make_source("tariffpeg/x.py", f'"""x."""\n\n\ndef f() -> None:\n{body}')


def test_the_real_tree_raises_its_refusals_properly() -> None:
    assert check_errors.problems() == []


def test_a_refusal_built_properly_reads_clean(plant: Planter) -> None:
    plant(check_errors, "source_files", [source('    raise Invalid("x", 1, "this will not do")\n')])
    assert check_errors.problems() == []


def test_a_refusal_built_from_the_wrong_number_of_pieces_is_reported(plant: Planter) -> None:
    plant(check_errors, "source_files", [source('    raise Invalid("x", 1)\n')])
    found = check_errors.problems()
    assert len(found) == 1
    assert "builds Invalid from 2 pieces, not 3" in found[0]


def test_a_not_found_with_one_piece_is_reported(plant: Planter) -> None:
    plant(check_errors, "source_files", [source('    raise NotFound("licence")\n')])
    assert any("builds NotFound from 1 pieces" in problem for problem in check_errors.problems())


def test_a_reason_that_ends_with_a_full_stop_is_reported(plant: Planter) -> None:
    plant(check_errors, "source_files", [source('    raise Invalid("x", 1, "no good.")\n')])
    assert any("ends with a full stop" in problem for problem in check_errors.problems())


def test_a_reason_that_starts_with_a_capital_is_reported(plant: Planter) -> None:
    plant(check_errors, "source_files", [source('    raise Invalid("x", 1, "No good")\n')])
    assert any("starts with a capital" in problem for problem in check_errors.problems())


def test_a_blank_reason_is_reported(plant: Planter) -> None:
    plant(check_errors, "source_files", [source('    raise Invalid("x", 1, "  ")\n')])
    assert any("is blank" in problem for problem in check_errors.problems())


def test_a_reason_that_is_not_a_plain_string_is_left_alone(plant: Planter) -> None:
    plant(check_errors, "source_files", [source('    raise Invalid("x", 1, f"no {1} good")\n')])
    assert check_errors.problems() == []


def test_raising_a_bare_exception_is_reported(plant: Planter) -> None:
    plant(check_errors, "source_files", [source('    raise Exception("something")\n')])
    found = check_errors.problems()
    assert found == ["src/tariffpeg/x.py:5 raises Exception"]


def test_raising_a_runtime_error_is_reported(plant: Planter) -> None:
    plant(check_errors, "source_files", [source('    raise RuntimeError("something")\n')])
    assert any("raises RuntimeError" in problem for problem in check_errors.problems())


def test_raising_not_implemented_is_reported(plant: Planter) -> None:
    plant(check_errors, "source_files", [source("    raise NotImplementedError\n")])
    assert any("raises NotImplementedError" in problem for problem in check_errors.problems())


def test_a_refusal_raised_by_its_qualified_name_is_still_checked(plant: Planter) -> None:
    plant(check_errors, "source_files", [source('    raise errors.Invalid("x", 1)\n')])
    assert any("builds Invalid" in problem for problem in check_errors.problems())


def test_a_bare_reraise_is_left_alone(plant: Planter) -> None:
    body = "    try:\n        pass\n    except ValueError:\n        raise\n"
    plant(check_errors, "source_files", [source(body)])
    assert check_errors.problems() == []


def test_an_exception_nobody_listed_is_left_alone(plant: Planter) -> None:
    plant(check_errors, "source_files", [source('    raise ValueError("something")\n')])
    assert check_errors.problems() == []


def test_every_refusal_in_the_hierarchy_is_in_the_table() -> None:
    from tariffpeg.errors import TariffpegError

    names = {kind.__name__ for kind in TariffpegError.__subclasses__()}
    assert names == set(check_errors.WANTED)


def test_the_check_exits_nothing_on_a_clean_tree() -> None:
    assert check_errors.main() == 0
