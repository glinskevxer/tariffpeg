"""A row with a bad date in it should not stop the other four hundred."""

from __future__ import annotations

from tariffpeg.model.licence import LicenceStatus
from tariffpeg.normalise.register import read_text

HEADER = "serial,trading_name,operator_name,locality,period_start,period_end"
GOOD = (
    f"{HEADER},closed_months,status,operator_ref,grading_band,let_rooms,bed_spaces,lift\n"
    "4021,The Anchor Rooms,Pellow and Daughter,Porthgwarra,2025-04-01,2026-03-31,"
    '"1,2",active,pellow-and-daughter,3,9,18,yes\n'
    "5000,Quay Cottage,Trewin Lets,Sennen,2025-04-01,2026-03-31,,active,trewin-lets,2,4,8,no\n"
)


def test_an_extract_reads_into_licences() -> None:
    reading = read_text(GOOD)
    assert reading.ok
    assert [licence.serial for licence in reading.licences] == [4021, 5000]
    assert reading.summary() == "2 rows read, 0 refused"


def test_the_particular_columns_are_whatever_the_header_says() -> None:
    licence = read_text(GOOD).licences[0]
    assert licence.particular("grading_band") == 3
    assert licence.particular("lift") is True
    assert read_text(GOOD).licences[1].particular("lift") is False


def test_the_closed_months_are_read_off_the_row() -> None:
    reading = read_text(GOOD)
    assert reading.licences[0].closed_months == frozenset({1, 2})
    assert reading.licences[1].closed_months == frozenset()


def test_the_status_and_the_operator_are_read_off_the_row() -> None:
    licence = read_text(GOOD).licences[0]
    assert licence.status is LicenceStatus.ACTIVE
    assert licence.operator_ref == "pellow-and-daughter"


def test_a_row_with_no_status_is_read_as_active() -> None:
    text = GOOD.replace(",active,pellow", ",,pellow")
    assert read_text(text).licences[0].status is LicenceStatus.ACTIVE


def test_a_row_that_will_not_read_is_refused_and_the_rest_go_through() -> None:
    text = GOOD.replace('2025-04-01,2026-03-31,"1,2"', 'not a date,2026-03-31,"1,2"')
    reading = read_text(text)
    assert len(reading.licences) == 1
    assert len(reading.problems) == 1
    assert reading.problems[0].startswith("row 2:")
    assert not reading.ok


def test_a_row_the_licence_rules_refuse_is_named_with_its_number() -> None:
    text = GOOD.replace(",3,9,18,yes", ",9,9,18,yes")
    reading = read_text(text)
    assert any("one to five" in problem for problem in reading.problems)


def test_a_row_missing_a_mandatory_particular_is_refused() -> None:
    text = GOOD.replace(",grading_band,let_rooms,bed_spaces,lift", ",grading_band,let_rooms,lift")
    text = text.replace(",3,9,18,yes", ",3,9,yes").replace(",2,4,8,no", ",2,4,no")
    reading = read_text(text)
    assert len(reading.problems) == 2
    assert all("required on every licence" in problem for problem in reading.problems)


def test_an_extract_with_no_header_row_is_refused() -> None:
    reading = read_text("")
    assert reading.problems == ["the extract has no header row"]


def test_an_extract_missing_a_column_it_has_to_carry_is_refused() -> None:
    reading = read_text(HEADER.replace("locality,", "") + "\n")
    assert reading.problems == ["the extract has no locality column"]


def test_an_extract_carrying_a_column_nobody_reads_is_refused() -> None:
    reading = read_text(f"{HEADER},sauna\n")
    assert reading.problems == ["the extract carries a column nobody reads: sauna"]


def test_an_extract_with_only_a_header_reads_nothing_and_refuses_nothing() -> None:
    reading = read_text(f"{HEADER},grading_band,let_rooms,bed_spaces\n")
    assert reading.ok
    assert reading.licences == []
