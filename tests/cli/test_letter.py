"""What went out, when the reply was due, and whether it came."""

from __future__ import annotations

from tariffpeg.cli.letter import digest_of
from tests.cli.conftest import Run
from tests.cli.test_channel import ADD_LICENCE, REF
from tests.cli.test_operator import ADD_OPERATOR

SEND = (
    "letter",
    "send",
    "DE-2026-0044",
    REF,
    "--kind",
    "desk enquiry",
    "--subject",
    "The passenger lift at The Anchor Rooms",
    "--body",
    "Dear Ms Pellow, we have had two reports about the lift.",
    "--on",
    "2026-06-01",
)


def stocked(run: Run) -> None:
    run(*ADD_OPERATOR)
    run(*ADD_LICENCE)
    run("operator", "hold", REF, "pellow-and-daughter")


def test_the_digest_of_a_letter_depends_on_what_it_said() -> None:
    assert digest_of("one").startswith("sha256:")
    assert digest_of("one") != digest_of("two")
    assert digest_of("one") == digest_of("one")


def test_a_letter_is_recorded_with_the_day_a_reply_is_due(migrated: Run) -> None:
    stocked(migrated)
    result = migrated(*SEND)
    assert result.exit_code == 0
    assert "sent to R Pellow, Pellow and Daughter" in result.output
    assert "reply due 2026-06-19" in result.output


def test_a_letter_reads_back_off_the_register(migrated: Run) -> None:
    stocked(migrated)
    migrated(*SEND)
    listed = migrated("letter", "list")
    assert "DE-2026-0044" in listed.output
    assert "desk enquiry" in listed.output
    assert "passenger lift" in listed.output


def test_a_letter_about_a_licence_with_no_operator_is_refused(migrated: Run) -> None:
    migrated(*ADD_LICENCE)
    result = migrated(*SEND)
    assert result.exit_code == 3


def test_the_same_reference_twice_is_refused(migrated: Run) -> None:
    stocked(migrated)
    migrated(*SEND)
    assert migrated(*SEND).exit_code == 4


def test_a_reply_is_recorded_against_the_letter(migrated: Run) -> None:
    stocked(migrated)
    migrated(*SEND)
    result = migrated("letter", "reply", "DE-2026-0044", "--on", "2026-06-08")
    assert result.exit_code == 0
    assert "answered on 2026-06-08" in result.output
    assert "late" not in result.output


def test_a_reply_that_came_after_it_was_due_says_it_was_late(migrated: Run) -> None:
    stocked(migrated)
    migrated(*SEND)
    result = migrated("letter", "reply", "DE-2026-0044", "--on", "2026-07-01")
    assert "and it was late" in result.output


def test_a_reply_to_a_letter_nobody_sent_is_refused(migrated: Run) -> None:
    stocked(migrated)
    assert migrated("letter", "reply", "DE-9999").exit_code == 3


def test_the_unanswered_letters_can_be_asked_for(migrated: Run) -> None:
    stocked(migrated)
    migrated(*SEND)
    assert "DE-2026-0044" in migrated("letter", "list", "--unanswered").output
    migrated("letter", "reply", "DE-2026-0044", "--on", "2026-06-08")
    assert "nothing has gone out" in migrated("letter", "list", "--unanswered").output


def test_the_letters_about_one_licence_can_be_asked_for(migrated: Run) -> None:
    stocked(migrated)
    migrated(*SEND)
    assert "DE-2026-0044" in migrated("letter", "list", "--licence", REF).output


def test_the_letters_to_one_operator_can_be_asked_for(migrated: Run) -> None:
    stocked(migrated)
    migrated(*SEND)
    found = migrated("letter", "list", "--operator", "pellow-and-daughter")
    assert "DE-2026-0044" in found.output


def test_a_register_with_nothing_in_it_says_so(migrated: Run) -> None:
    assert "nothing has gone out" in migrated("letter", "list").output


def test_the_overdue_letters_are_the_ones_nobody_answered_in_time(migrated: Run) -> None:
    stocked(migrated)
    migrated(*SEND)
    assert "answered in time" in migrated("letter", "overdue", "--on", "2026-06-19").output
    late = migrated("letter", "overdue", "--on", "2026-06-22")
    assert "DE-2026-0044" in late.output


def test_a_letter_that_was_answered_never_shows_up_as_overdue(migrated: Run) -> None:
    stocked(migrated)
    migrated(*SEND)
    migrated("letter", "reply", "DE-2026-0044", "--on", "2026-06-08")
    assert "answered in time" in migrated("letter", "overdue", "--on", "2027-01-01").output


def test_a_kind_of_letter_nobody_recognises_is_refused(migrated: Run) -> None:
    stocked(migrated)
    result = migrated(*SEND[:6], "--kind", "postcard", *SEND[8:])
    assert result.exit_code != 0
