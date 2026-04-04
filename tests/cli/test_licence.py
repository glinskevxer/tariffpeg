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


EXTRACT = (
    "serial,trading_name,operator_name,locality,period_start,period_end,"
    "grading_band,let_rooms,bed_spaces\n"
    "4021,The Anchor Rooms,Pellow and Daughter,Porthgwarra,2025-04-01,2026-03-31,3,9,18\n"
    "5000,Quay Cottage,Trewin Lets,Sennen,2025-04-01,2026-03-31,2,4,8\n"
)


def test_an_extract_is_read_onto_the_register(migrated: Run, tmp_path: Path) -> None:
    target = tmp_path / "register.csv"
    target.write_text(EXTRACT, encoding="utf-8")
    result = migrated("licence", "import", str(target))
    assert result.exit_code == 0
    assert "2 rows read, 0 refused" in result.output
    assert "2 added" in result.output
    assert "Quay Cottage" in migrated("licence", "list").output


def test_a_dry_run_writes_nothing(migrated: Run, tmp_path: Path) -> None:
    target = tmp_path / "register.csv"
    target.write_text(EXTRACT, encoding="utf-8")
    result = migrated("licence", "import", str(target), "--dry-run")
    assert "nothing was written" in result.output
    assert "Quay Cottage" not in migrated("licence", "list").output


def test_a_licence_already_on_the_register_is_left_alone(migrated: Run, tmp_path: Path) -> None:
    target = tmp_path / "register.csv"
    target.write_text(EXTRACT, encoding="utf-8")
    migrated("licence", "import", str(target))
    again = migrated("licence", "import", str(target))
    assert "0 added, 0 written over, 2 left alone" in again.output


def test_a_licence_already_on_the_register_is_written_over_when_asked(
    migrated: Run, tmp_path: Path
) -> None:
    target = tmp_path / "register.csv"
    target.write_text(EXTRACT, encoding="utf-8")
    migrated("licence", "import", str(target))
    target.write_text(EXTRACT.replace("The Anchor Rooms", "The Anchor Hotel"), encoding="utf-8")
    again = migrated("licence", "import", str(target), "--replace")
    assert "2 written over" in again.output
    assert "The Anchor Hotel" in migrated("licence", "list").output


def test_a_row_that_will_not_read_is_named_and_the_rest_go_on(
    migrated: Run, tmp_path: Path
) -> None:
    target = tmp_path / "register.csv"
    target.write_text(
        EXTRACT.replace("2025-04-01,2026-03-31,3", "nonsense,2026-03-31,3"), encoding="utf-8"
    )
    result = migrated("licence", "import", str(target))
    assert "1 rows read, 1 refused" in result.output
    assert "row 2:" in result.output
    assert "1 added" in result.output


def test_an_extract_that_is_not_there_is_refused(migrated: Run, tmp_path: Path) -> None:
    result = migrated("licence", "import", str(tmp_path / "nothing.csv"))
    assert result.exit_code == 2
    assert "no extract here" in result.output
