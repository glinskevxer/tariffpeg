"""A trading name cut off at twenty characters is one somebody has to look up again."""

from __future__ import annotations

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.report.rows import MISSING, Column, as_csv, render, totals, widths

COLUMNS = (
    Column("ref", "reference"),
    Column("name", "trading name"),
    Column("score", "score", numeric=True),
    Column("lift", "lift"),
)
ROWS = (
    {"ref": "L-004021-B", "name": "The Anchor Rooms", "score": 8.4567, "lift": True},
    {"ref": "L-000009-C", "name": "Quay", "score": 12.0, "lift": False},
)


def test_a_column_needs_a_field_and_a_heading() -> None:
    with pytest.raises(Invalid, match="reads a named field"):
        Column("  ", "x")
    with pytest.raises(Invalid, match="has a heading"):
        Column("x", "  ")


def test_negative_decimal_places_are_refused() -> None:
    with pytest.raises(Invalid, match="not negative"):
        Column("x", "X", places=-1)


def test_a_missing_value_prints_as_a_dash() -> None:
    assert Column("x", "X").render(None) == MISSING


def test_a_flag_prints_as_yes_or_no() -> None:
    assert Column("x", "X").render(True) == "yes"
    assert Column("x", "X").render(False) == "no"


def test_a_float_prints_to_the_places_the_column_asks_for() -> None:
    assert Column("x", "X").render(8.4567) == "8.46"
    assert Column("x", "X", places=0).render(8.4567) == "8"
    assert Column("x", "X", places=4).render(8.4567) == "8.4567"


def test_an_integer_prints_without_a_decimal_point() -> None:
    assert Column("x", "X", numeric=True).render(12) == "12"


def test_a_table_carries_a_heading_and_a_rule() -> None:
    lines = render(ROWS, COLUMNS)
    assert lines[0].startswith("reference")
    assert set(lines[1]) <= {"-", " "}
    assert len(lines) == 4


def test_nothing_is_truncated_however_long_it_is() -> None:
    lines = render(ROWS, COLUMNS)
    assert "The Anchor Rooms" in lines[2]


def test_a_column_is_as_wide_as_its_widest_cell_or_its_heading() -> None:
    sizes = widths(ROWS, COLUMNS)
    assert sizes[1] == len("The Anchor Rooms")
    assert sizes[3] == len("lift")


def test_a_table_with_no_rows_still_has_its_headings() -> None:
    lines = render((), COLUMNS)
    assert len(lines) == 2
    assert "trading name" in lines[0]


def test_numbers_go_right_and_words_go_left() -> None:
    lines = render(ROWS, COLUMNS)
    assert lines[2].split("  ")[0] == "L-004021-B"
    assert "8.46" in lines[2]
    assert lines[2].rstrip() == lines[2]


def test_a_row_that_is_missing_a_field_prints_a_dash() -> None:
    lines = render(({"ref": "L-004021-B"},), COLUMNS)
    assert MISSING in lines[2]


def test_a_table_with_no_columns_is_refused() -> None:
    with pytest.raises(Invalid, match="needs a column"):
        render(ROWS, ())
    with pytest.raises(Invalid, match="needs a column"):
        as_csv(ROWS, ())


def test_the_comma_separated_form_carries_the_same_headings() -> None:
    text = as_csv(ROWS, COLUMNS)
    lines = text.splitlines()
    assert lines[0] == "reference,trading name,score,lift"
    assert lines[1].startswith("L-004021-B,The Anchor Rooms,8.46,yes")
    assert len(lines) == 3


def test_the_comma_separated_form_quotes_what_needs_quoting() -> None:
    text = as_csv(({"ref": "a,b", "name": "x", "score": 1.0, "lift": True},), COLUMNS)
    assert '"a,b"' in text


def test_a_column_can_be_totalled_across_the_rows() -> None:
    assert totals(ROWS, "score") == pytest.approx(20.4567)


def test_totalling_skips_rows_with_nothing_and_flags() -> None:
    rows: tuple[dict[str, object], ...] = (
        {"score": 1.0},
        {"score": None},
        {},
        {"score": True},
    )
    assert totals(rows, "score") == 1.0


def test_totalling_a_column_nobody_has_gives_nothing() -> None:
    assert totals(ROWS, "nothing") == 0.0
