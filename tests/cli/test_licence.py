"""The register is typed in by hand, so the refusals have to read plainly."""

from __future__ import annotations

from pathlib import Path

from tariffpeg.ids import format_licence_ref
from tests.cli.conftest import Run

REF = format_licence_ref(4021)
ADD = (
    "licence",
    "add",
    "4021",
    "--name",
    "The Anchor Rooms",
    "--operator",
    "Pellow and Daughter",
    "--locality",
    "Porthgwarra",
    "--from",
    "2025-04-01",
    "--to",
    "2026-03-31",
    "--closed",
    "1,2",
    "--particular",
    "grading_band=3",
    "--particular",
    "let_rooms=9",
    "--particular",
    "bed_spaces=18",
    "--particular",
    "lift=yes",
)


def test_a_licence_is_added_and_reads_back(migrated: Run) -> None:
    result = migrated(*ADD)
    assert result.exit_code == 0
    assert REF in result.output
    listed = migrated("licence", "list")
    assert "The Anchor Rooms" in listed.output
    assert "Porthgwarra" in listed.output


def test_the_same_serial_twice_is_refused_with_its_own_exit_code(migrated: Run) -> None:
    migrated(*ADD)
    result = migrated(*ADD)
    assert result.exit_code == 4
    assert "already registered" in result.output


def test_a_particular_written_wrongly_is_refused(migrated: Run) -> None:
    result = migrated(*ADD, "--particular", "lift")
    assert result.exit_code == 2
    assert "key=value" in result.output


def test_a_particular_nobody_registers_is_refused(migrated: Run) -> None:
    result = migrated(*ADD, "--particular", "sauna=yes")
    assert result.exit_code == 2
    assert "no such particular" in result.output


def test_a_licence_missing_a_mandatory_particular_is_refused(migrated: Run) -> None:
    result = migrated(
        "licence",
        "add",
        "9",
        "--name",
        "X",
        "--operator",
        "Y",
        "--locality",
        "Z",
        "--from",
        "2025-04-01",
        "--to",
        "2026-03-31",
        "--particular",
        "lift=yes",
    )
    assert result.exit_code == 2
    assert "required on every licence" in result.output


def test_showing_a_licence_prints_its_particulars(migrated: Run) -> None:
    migrated(*ADD)
    result = migrated("licence", "show", REF)
    assert result.exit_code == 0
    assert "The Anchor Rooms" in result.output
    assert "passenger lift" in result.output
    assert "open in months 3, 4" in result.output


def test_showing_a_licence_nobody_registered_is_refused(migrated: Run) -> None:
    result = migrated("licence", "show", format_licence_ref(9999))
    assert result.exit_code == 3
    assert "not_found" in result.output


def test_a_reference_with_the_wrong_check_character_is_refused(migrated: Run) -> None:
    wrong = REF[:-1] + ("Z" if REF[-1] != "Z" else "B")
    result = migrated("licence", "show", wrong)
    assert result.exit_code == 3


def test_a_licence_can_be_varied(migrated: Run) -> None:
    migrated(*ADD)
    result = migrated("licence", "vary", REF, "--particular", "lift=no")
    assert result.exit_code == 0
    shown = migrated("licence", "show", REF)
    assert "lift" in shown.output
    assert "no" in shown.output


def test_a_licence_can_be_moved_into_another_status(migrated: Run) -> None:
    migrated(*ADD)
    result = migrated("licence", "status", REF, "lapsed")
    assert result.exit_code == 0
    listed = migrated("licence", "list", "--status", "lapsed")
    assert REF in listed.output
    assert migrated("licence", "list", "--status", "active").output.count(REF) == 0


def test_a_status_nobody_recognises_is_refused(migrated: Run) -> None:
    migrated(*ADD)
    result = migrated("licence", "status", REF, "sideways")
    assert result.exit_code != 0


def test_the_register_can_be_read_a_locality_at_a_time(migrated: Run) -> None:
    migrated(*ADD)
    assert REF in migrated("licence", "list", "--locality", "Porthgwarra").output
    assert REF not in migrated("licence", "list", "--locality", "Sennen").output


def test_the_particulars_the_order_recognises_are_listed(migrated: Run) -> None:
    result = migrated("licence", "particulars")
    assert result.exit_code == 0
    assert "grading_band" in result.output
    assert "shore_distance" in result.output


def test_a_licence_can_be_taken_off_the_register(migrated: Run) -> None:
    migrated(*ADD)
    result = migrated("licence", "remove", REF, "--yes")
    assert result.exit_code == 0
    assert REF not in migrated("licence", "list").output


def test_removing_without_confirming_leaves_it_alone(migrated: Run) -> None:
    migrated(*ADD)
    result = migrated("licence", "remove", REF)
    assert result.exit_code != 0
    assert REF in migrated("licence", "list").output


def test_the_register_can_be_asked_for_as_comma_separated_text(migrated: Run) -> None:
    migrated(*ADD)
    result = migrated("licence", "list", extra=["--csv"])
    assert result.output.splitlines()[0] == "reference,trading name,locality,keys,rooms,status"


def test_the_settings_in_force_are_printed(migrated: Run) -> None:
    result = migrated("config", "show")
    assert result.exit_code == 0
    assert "crawl_delay_ms" in result.output


def test_only_the_changed_settings_are_printed_when_that_is_asked_for(migrated: Run) -> None:
    result = migrated("config", "show", "--changed-only")
    assert "every setting is at its default" in result.output


def test_the_defaults_are_printed_on_their_own(migrated: Run) -> None:
    assert "inspectors" in migrated("config", "defaults").output


def test_a_settings_file_can_be_checked(migrated: Run, tmp_path: Path) -> None:
    target = tmp_path / "tariffpeg.toml"
    target.write_text("[tariffpeg]\ncrawl_delay_ms = 5000\n", encoding="utf-8")
    result = migrated("config", "check", str(target))
    assert result.exit_code == 0
    assert "1 settings changed" in result.output
    assert "crawl_delay_ms = 5000" in result.output


def test_a_settings_file_with_a_typo_is_refused(migrated: Run, tmp_path: Path) -> None:
    target = tmp_path / "tariffpeg.toml"
    target.write_text("[tariffpeg]\ncrawl_delay_millis = 5000\n", encoding="utf-8")
    result = migrated("config", "check", str(target))
    assert result.exit_code == 2
    assert "no such key" in result.output
