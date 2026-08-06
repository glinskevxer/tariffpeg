"""A letter says the same thing the file says, in the operator's terms."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.claims.pack import PACK
from tariffpeg.errors import Conflict
from tariffpeg.model.channel import Channel
from tariffpeg.model.determination import Determination
from tariffpeg.model.letter import Sent
from tariffpeg.model.licence import Licence
from tariffpeg.model.outcome import Disposition
from tariffpeg.model.period import StayMonth
from tariffpeg.report.casefile import build
from tariffpeg.report.notice import KIND_FOR, QUOTES_PER_FINDING, Draft, draft
from tests.report.test_casefile import AT, captures, coverage, reviews
from tests.triage.conftest import a_review

SENT_ON = dt.date(2025, 10, 2)
MINUTED = dt.datetime(2025, 10, 2, 9, 30, tzinfo=dt.UTC)


def minute(serial: int = 4021) -> Determination:
    return Determination(
        licence_serial=serial,
        decided_at=StayMonth(2025, 9),
        disposition=Disposition.DESK_ENQUIRY,
        score=4.5,
        access_score=0.0,
        capped=False,
        pack_version=PACK.version,
        minuted_at=MINUTED,
        officer="R Bosustow",
    )


def a_case(anchor: Licence, channels: dict[str, Channel], satisfied: bool = True) -> object:
    return build(anchor, reviews(), channels, coverage(satisfied), [], PACK, AT, captures())


def test_every_disposition_that_sends_a_letter_has_a_kind_for_it() -> None:
    assert set(KIND_FOR) == {
        Disposition.DESK_ENQUIRY,
        Disposition.REINSPECTION,
        Disposition.URGENT,
    }
    assert Disposition.NO_ACTION not in KIND_FOR


def test_a_file_that_came_out_at_no_action_produces_no_letter(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    quiet = build(anchor, (a_review("1", "A fine week."),), channels, coverage(), [], PACK, AT)
    with pytest.raises(Conflict, match="does not produce a letter"):
        draft(quiet, None, SENT_ON)


def test_the_letter_names_the_licence_and_the_operator(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    letter = draft(a_case(anchor, channels), None, SENT_ON)  # type: ignore[arg-type]
    lines = letter.lines()
    assert anchor.ref in lines[0]
    assert anchor.operator_name in lines[1]
    assert anchor.trading_name in letter.subject


def test_the_letter_quotes_what_guests_wrote(anchor: Licence, channels: dict[str, Channel]) -> None:
    letter = draft(a_case(anchor, channels), None, SENT_ON)  # type: ignore[arg-type]
    body = "\n".join(letter.paragraphs)
    assert "lift" in body
    assert '"' in body


def test_no_finding_puts_more_than_three_quotations_in_the_letter(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    letter = draft(a_case(anchor, channels), None, SENT_ON)  # type: ignore[arg-type]
    for paragraph in letter.paragraphs:
        assert paragraph.count('"') <= QUOTES_PER_FINDING * 2


def test_a_letter_that_follows_a_minute_says_which_minute(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    letter = draft(a_case(anchor, channels), minute(), SENT_ON)  # type: ignore[arg-type]
    body = "\n".join(letter.paragraphs)
    assert "minuted on 2025-09" in body
    assert f"rule pack {PACK.version}" in body


def test_a_letter_with_no_minute_behind_it_does_not_mention_one(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    letter = draft(a_case(anchor, channels), None, SENT_ON)  # type: ignore[arg-type]
    assert "minuted on" not in "\n".join(letter.paragraphs)


def test_a_letter_off_an_incomplete_sample_asks_rather_than_concludes(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    letter = draft(a_case(anchor, channels, satisfied=False), None, SENT_ON)  # type: ignore[arg-type]
    assert any("asks a question rather than" in paragraph for paragraph in letter.paragraphs)


def test_the_reply_day_is_the_one_the_kind_of_letter_allows(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    letter = draft(a_case(anchor, channels), None, SENT_ON)  # type: ignore[arg-type]
    assert letter.reply_by > SENT_ON
    assert str(letter.reply_by) in letter.lines()[-1]


def test_the_whole_letter_comes_back_as_one_block_that_can_be_hashed(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    letter = draft(a_case(anchor, channels), None, SENT_ON)  # type: ignore[arg-type]
    assert letter.text().endswith("\n")
    assert letter.text().count("\n") >= len(letter.lines())
    assert letter.kind is Sent.NOTICE_OF_INSPECTION


def test_a_file_that_sends_somebody_out_tells_the_operator_a_visit_is_coming(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    letter = draft(a_case(anchor, channels), None, SENT_ON)  # type: ignore[arg-type]
    assert any("An officer will visit" in paragraph for paragraph in letter.paragraphs)


def test_a_letter_written_by_hand_prints_the_same_way_as_a_drafted_one() -> None:
    letter = Draft(
        licence_serial=4021,
        licence_ref="L-004021-M",
        operator_name="Pellow and Daughter",
        kind=Sent.DESK_ENQUIRY,
        subject="Accommodation standards: The Anchor Rooms",
        paragraphs=("We have reviewed what guests have written.",),
        reply_by=dt.date(2025, 10, 23),
    )
    lines = letter.lines()
    assert lines[0] == "Our reference: L-004021-M"
    assert lines[-1] == "Please reply by 2025-10-23."
