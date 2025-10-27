"""The register is typed in by hand, so the refusals have to read plainly."""

from __future__ import annotations

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


def test_a_particular_pair_is_read_into_a_value() -> None:
    from tariffpeg.cli.licence import as_row, parse_particulars

    assert parse_particulars(("lift=yes", "let_rooms=9")) == {"lift": True, "let_rooms": 9}
    import datetime as dt

    from tariffpeg.model.licence import Licence

    licence = Licence(
        serial=4021,
        trading_name="The Anchor Rooms",
        operator_name="Pellow and Daughter",
        locality="Porthgwarra",
        period_start=dt.date(2025, 4, 1),
        period_end=dt.date(2026, 3, 31),
        particulars={"grading_band": 3, "let_rooms": 9, "bed_spaces": 18},
    )
    assert as_row(licence)["ref"] == licence.ref
    assert as_row(licence)["band"] == 3
