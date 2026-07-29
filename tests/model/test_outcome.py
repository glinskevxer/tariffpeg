"""A disposition read back out of an old file has to mean what it meant then."""

from __future__ import annotations

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.model.outcome import (
    ORDER,
    SENDS_SOMEBODY_OUT,
    Disposition,
    heavier,
    parse_disposition,
    rank,
)


def test_the_order_runs_from_nothing_happening_to_somebody_going_out_today() -> None:
    assert ORDER[0] is Disposition.NO_ACTION
    assert ORDER[-1] is Disposition.URGENT
    assert len(ORDER) == len(set(ORDER)) == 4


def test_the_heavier_of_two_dispositions_is_the_one_further_up_the_order() -> None:
    assert heavier(Disposition.NO_ACTION, Disposition.URGENT) is Disposition.URGENT
    assert heavier(Disposition.REINSPECTION, Disposition.DESK_ENQUIRY) is Disposition.REINSPECTION


def test_a_disposition_is_not_heavier_than_itself() -> None:
    assert heavier(Disposition.DESK_ENQUIRY, Disposition.DESK_ENQUIRY) is Disposition.DESK_ENQUIRY


def test_the_rank_counts_from_nought_in_order() -> None:
    assert [rank(item) for item in ORDER] == [0, 1, 2, 3]


def test_only_the_two_heaviest_dispositions_send_anybody_out() -> None:
    assert {Disposition.REINSPECTION, Disposition.URGENT} == SENDS_SOMEBODY_OUT


def test_a_stored_disposition_reads_back_as_the_one_that_was_written() -> None:
    for disposition in ORDER:
        assert parse_disposition(disposition.value) is disposition


def test_a_word_the_order_does_not_carry_is_refused_rather_than_read_as_nothing() -> None:
    with pytest.raises(Invalid, match="not a disposition the order carries"):
        parse_disposition("referred to committee")


def test_an_empty_disposition_is_refused_too() -> None:
    with pytest.raises(Invalid, match="not a disposition the order carries"):
        parse_disposition("")
