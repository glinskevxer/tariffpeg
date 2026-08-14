"""What the unit would do about each licence, on the command line."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from tariffpeg.cli.context import Context
from tariffpeg.cli.triage import diaries_of, minute_row, visit_row
from tariffpeg.ids import format_licence_ref
from tariffpeg.model.determination import Determination
from tariffpeg.model.outcome import Disposition
from tariffpeg.model.period import StayMonth
from tariffpeg.settings import DEFAULTS
from tariffpeg.triage.schedule import Booking
from tests.cli.conftest import Run
from tests.cli.harvest_setup import REF, stock, write_bundle, write_profiles


def harvested(run: Run, tmp_path: Path) -> None:
    stock(run)
    run(
        "harvest",
        "run",
        "--profiles",
        str(write_profiles(tmp_path)),
        "--bundle",
        str(write_bundle(tmp_path)),
        "--on",
        "2025-09-15",
    )


def test_the_triage_list_says_what_would_happen(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "list", "--at", "2025-09")
    assert result.exit_code == 0
    assert "4021" in result.output
    assert "The Anchor Rooms" in result.output


def test_the_triage_list_can_be_narrowed_to_visits(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "list", "--at", "2025-09", "--needing-a-visit")
    assert "nothing needs doing" in result.output


def test_the_findings_behind_a_decision_are_printed(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "show", REF, "--at", "2025-09")
    assert result.exit_code == 0
    assert "the evidence scores" in result.output
    assert "lift" in result.output


def test_a_licence_with_nothing_against_it_says_so(run: Run) -> None:
    stock(run)
    result = run("triage", "show", REF, "--at", "2025-09")
    assert "nothing was found against the particulars" in result.output


def test_the_schedule_books_nothing_when_nothing_needs_a_visit(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "schedule", "--at", "2025-09", "--on", "2025-09-15")
    assert result.exit_code == 0
    assert "nothing needs a visit" in result.output


def test_the_triage_list_can_be_asked_for_as_comma_separated_text(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "list", "--at", "2025-09", extra=["--csv"])
    assert result.output.splitlines()[0].startswith("licence,trading name,disposition")


def test_a_month_the_reader_does_not_know_is_refused(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "list", "--at", "last summer")
    assert result.exit_code == 2
    assert "not a shape this reader knows" in result.output


def test_the_monthly_return_prints_the_figures(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "return", "--at", "2025-09")
    assert result.exit_code == 0
    assert "Return for 2025-09" in result.output
    assert "licences on the register" in result.output
    assert "held back by a short sample" in result.output


def test_the_monthly_return_counts_the_licence_that_is_there(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    lines = run("triage", "return", "--at", "2025-09").output.splitlines()
    listed = [line for line in lines if "licences on the register" in line]
    assert listed[0].rstrip().endswith("1")


def test_the_monthly_return_can_be_asked_for_as_comma_separated_text(
    run: Run, tmp_path: Path
) -> None:
    harvested(run, tmp_path)
    result = run("triage", "return", "--at", "2025-09", extra=["--csv"])
    assert "figure,count" in result.output


def test_the_explanation_shows_the_steps(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "explain", REF, "--at", "2025-09")
    assert result.exit_code == 0
    assert "WHAT WAS FOUND" in result.output
    assert "HOW IT WAS ADDED UP" in result.output
    assert "rule lift-absent" in result.output


def test_the_explanation_of_a_licence_nobody_registered_is_refused(run: Run) -> None:
    stock(run)
    from tariffpeg.ids import format_licence_ref

    assert run("triage", "explain", format_licence_ref(9999)).exit_code == 3


def test_the_locality_breakdown_prints_one_row_per_place(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "locality", "--at", "2025-09")
    assert result.exit_code == 0
    assert "Porthgwarra" in result.output
    assert "worst disposition" in result.output


def test_the_locality_breakdown_names_the_places_with_nothing_sampled(
    run: Run, tmp_path: Path
) -> None:
    harvested(run, tmp_path)
    result = run("triage", "locality", "--at", "2025-09")
    assert "nothing is properly sampled in: Porthgwarra" in result.output


def test_a_register_with_no_active_licence_says_so(run: Run) -> None:
    run("db", "migrate")
    assert "no active licence is on the register" in run("triage", "locality").output


def test_the_decisions_can_be_taken_under_an_older_pack(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "list", "--at", "2025-08", "--pack", "1")
    assert result.exit_code == 0


def test_an_explanation_can_be_taken_under_an_older_pack(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "explain", REF, "--at", "2025-08", "--pack", "1")
    assert result.exit_code == 0


def test_a_decision_cannot_be_taken_under_a_pack_nobody_published(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "list", "--at", "2025-08", "--pack", "44")
    assert result.exit_code == 3


def test_the_workload_says_there_is_nothing_to_spread_when_nobody_goes_out(
    run: Run, tmp_path: Path
) -> None:
    harvested(run, tmp_path)
    result = run("triage", "workload", "--at", "2025-09", "--on", "2025-09-15")
    assert result.exit_code == 0
    assert "nothing to spread" in result.output


def test_the_workload_reads_the_inspectors_out_of_the_settings(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "workload", "--at", "2025-08", "--on", "2025-08-15")
    assert result.exit_code == 0


def test_a_diary_is_opened_for_each_inspector_the_settings_name(tmp_path: Path) -> None:
    ctx = Context(tmp_path / "evidence.sqlite3", DEFAULTS)
    found = diaries_of(ctx)
    assert [diary.name for diary in found] == list(DEFAULTS.inspectors)
    assert all(diary.weekly_capacity == DEFAULTS.weekly_capacity for diary in found)


def test_a_booked_visit_prints_whether_it_made_its_target() -> None:
    booking = Booking(4021, "Trewin", dt.date(2025, 9, 18), Disposition.URGENT)
    assert visit_row(booking, frozenset())["late"] is False
    assert visit_row(booking, frozenset({4021}))["late"] is True


def test_a_month_is_minuted_once_and_the_second_run_says_so(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    first = run("triage", "minute", "--at", "2025-09", "--officer", "R Bosustow")
    assert first.exit_code == 0
    assert "R Bosustow" in first.output
    again = run("triage", "minute", "--at", "2025-09", "--officer", "R Bosustow")
    assert "already minuted for every licence" in again.output


def test_a_minute_cannot_be_taken_without_saying_who_took_it(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "minute", "--at", "2025-09")
    assert result.exit_code == 2


def test_the_ledger_is_empty_until_a_month_has_been_minuted(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "ledger", REF)
    assert result.exit_code == 0
    assert "nothing has been minuted" in result.output


def test_the_ledger_says_how_each_minute_moved_against_the_one_before(
    run: Run, tmp_path: Path
) -> None:
    harvested(run, tmp_path)
    run("triage", "minute", "--at", "2025-08", "--officer", "R Bosustow")
    run("triage", "minute", "--at", "2025-09", "--officer", "R Bosustow")
    result = run("triage", "ledger", REF)
    assert result.exit_code == 0
    assert "held" in result.output


def test_the_ledger_of_a_licence_nobody_has_heard_of_is_refused(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "ledger", format_licence_ref(9999))
    assert result.exit_code == 3


def test_a_minute_prints_the_pack_it_was_taken_under() -> None:
    row = minute_row(
        Determination(
            licence_serial=4021,
            decided_at=StayMonth(2025, 9),
            disposition=Disposition.DESK_ENQUIRY,
            score=4.512,
            access_score=0.0,
            capped=False,
            pack_version=2,
            minuted_at=dt.datetime(2025, 10, 2, 9, 30, tzinfo=dt.UTC),
            officer="R Bosustow",
        ),
        "escalated",
    )
    assert row["pack"] == 2
    assert row["score"] == 4.51
    assert row["moved"] == "escalated"


def test_a_register_nobody_minuted_reconciles_as_never_minuted(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "reconcile", "--at", "2025-09")
    assert result.exit_code == 0
    assert "never been minuted" in result.output


def test_a_minuted_register_reconciles_as_still_reading_the_same_way(
    run: Run, tmp_path: Path
) -> None:
    harvested(run, tmp_path)
    run("triage", "minute", "--at", "2025-09", "--officer", "R Bosustow")
    result = run("triage", "reconcile", "--at", "2025-09")
    assert result.exit_code == 0
    assert "still reads the way it was minuted" in result.output


def test_the_list_can_be_narrowed_to_one_locality(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "list", "--at", "2025-08", "--locality", "Porthgwarra")
    assert result.exit_code == 0
    result = run("triage", "list", "--at", "2025-08", "--locality", "Zennor")
    assert "nothing needs doing" in result.output


def test_the_list_can_be_narrowed_to_one_disposition(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "list", "--at", "2025-08", "--disposition", "urgent re-inspection")
    assert result.exit_code == 0
    assert "nothing needs doing" in result.output


def test_a_disposition_the_order_does_not_carry_is_refused(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "list", "--at", "2025-08", "--disposition", "referred")
    assert result.exit_code == 2
