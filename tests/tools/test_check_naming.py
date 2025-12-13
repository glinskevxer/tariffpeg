"""A red line in the output should already be a sentence about what broke."""

from __future__ import annotations

from tariffpeg.tools import check_naming
from tariffpeg.tools.walk import SourceFile
from tests.tools.conftest import Planter, make_test

GOOD = '''"""What this file is about."""


def test_a_licence_with_no_lift_contradicts_one_that_claims_a_lift() -> None:
    pass


def helper() -> None:
    pass
'''


def one(text: str, name: str = "tests/x/test_thing.py") -> list[SourceFile]:
    return [make_test(name, text)]


def test_the_real_suite_names_what_it_is_asserting() -> None:
    assert check_naming.problems() == []


def test_a_name_that_says_what_is_true_reads_clean(plant: Planter) -> None:
    plant(check_naming, "suite_files", one(GOOD))
    assert check_naming.problems() == []


def test_a_name_with_too_few_words_in_it_is_reported(plant: Planter) -> None:
    text = GOOD.replace(
        "test_a_licence_with_no_lift_contradicts_one_that_claims_a_lift", "test_lift_works_here"
    )
    plant(check_naming, "suite_files", one(text))
    found = check_naming.problems()
    assert any("is 3 words, fewer than 5" in problem for problem in found)


def test_a_name_with_a_word_that_says_nothing_is_reported(plant: Planter) -> None:
    text = GOOD.replace(
        "test_a_licence_with_no_lift_contradicts_one_that_claims_a_lift",
        "test_the_lift_contradiction_is_handled_correctly_here",
    )
    plant(check_naming, "suite_files", one(text))
    found = check_naming.problems()
    assert any("says 'correctly'" in problem for problem in found)


def test_a_module_with_no_docstring_is_reported(plant: Planter) -> None:
    plant(check_naming, "suite_files", one("def test_a_b_c_d_e() -> None:\n    pass\n"))
    assert any("has no module docstring" in problem for problem in check_naming.problems())


def test_a_helper_that_is_not_a_test_is_left_alone(plant: Planter) -> None:
    plant(check_naming, "suite_files", one(GOOD))
    assert not any("helper" in problem for problem in check_naming.problems())


def test_a_file_that_is_not_a_test_file_is_left_alone(plant: Planter) -> None:
    plant(check_naming, "suite_files", one("A = 1\n", "tests/x/conftest.py"))
    assert check_naming.problems() == []


def test_the_words_of_a_name_leave_the_prefix_behind() -> None:
    assert check_naming.words_of("test_a_lift_that_is_out") == ["a", "lift", "that", "is", "out"]


def test_the_words_that_say_nothing_are_the_ones_this_repository_used() -> None:
    assert "works" in check_naming.VAGUE
    assert "properly" in check_naming.VAGUE
    assert "case" not in check_naming.VAGUE
    assert "test" not in check_naming.VAGUE


def test_the_check_exits_nothing_on_a_clean_suite() -> None:
    assert check_naming.main() == 0


def test_the_check_exits_one_when_it_finds_something(plant: Planter) -> None:
    plant(check_naming, "suite_files", one("def test_a_b() -> None:\n    pass\n"))
    assert check_naming.main() == 1
