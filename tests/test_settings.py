"""A misspelled key that quietly falls back to a default is the wrong failure."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.settings import DEFAULTS, Settings, describe, load, read_text

HOLIDAY_FILE = """[tariffpeg]
holidays = [2026-03-09]
"""


def test_the_defaults_stand_on_their_own() -> None:
    assert DEFAULTS.database.endswith(".sqlite3")
    assert DEFAULTS.crawl_delay_ms >= 250
    assert DEFAULTS.inspectors


def test_the_agent_string_is_built_from_the_name_and_the_contact() -> None:
    settings = Settings(agent_name="tariffpeg-harvester", contact="standards@example.test")
    assert settings.user_agent == "tariffpeg-harvester (standards@example.test)"


def test_a_contact_that_is_not_an_address_is_refused() -> None:
    with pytest.raises(Invalid, match="an address a channel can write to"):
        Settings(contact="ring the office")


def test_an_agent_string_with_no_name_is_refused() -> None:
    with pytest.raises(Invalid, match="needs a name in it"):
        Settings(agent_name="   ")


def test_a_crawl_delay_under_the_floor_is_refused() -> None:
    with pytest.raises(Invalid, match="floor for any channel"):
        Settings(crawl_delay_ms=100)


def test_a_setting_below_one_is_refused() -> None:
    for name in ("daily_request_ceiling", "max_pages_per_property"):
        with pytest.raises(Invalid, match="one or more"):
            Settings(**{name: 0})  # type: ignore[arg-type]
    with pytest.raises(Invalid, match="a month or more"):
        Settings(lookback_months=0)
    with pytest.raises(Invalid, match="needs one channel"):
        Settings(minimum_channels=0)
    with pytest.raises(Invalid, match="one visit or more"):
        Settings(weekly_capacity=0)


def test_a_unit_with_nobody_to_send_is_refused() -> None:
    with pytest.raises(Invalid, match="somebody to send"):
        Settings(inspectors=())


def test_an_inspector_named_twice_is_refused() -> None:
    with pytest.raises(Invalid, match="named once"):
        Settings(inspectors=("Trewin", "Trewin"))


def test_a_settings_file_changes_only_what_it_names() -> None:
    settings = read_text("[tariffpeg]\ncrawl_delay_ms = 5000\n")
    assert settings.crawl_delay_ms == 5000
    assert settings.daily_request_ceiling == DEFAULTS.daily_request_ceiling


def test_a_list_of_inspectors_is_read() -> None:
    settings = read_text('[tariffpeg]\ninspectors = ["Trewin", "Angove", "Bolitho"]\n')
    assert settings.inspectors == ("Trewin", "Angove", "Bolitho")


def test_inspectors_written_as_something_other_than_a_list_are_refused() -> None:
    with pytest.raises(Invalid, match="written as a list"):
        read_text('[tariffpeg]\ninspectors = "Trewin"\n')


def test_an_unknown_key_is_refused_by_name() -> None:
    with pytest.raises(Invalid) as caught:
        read_text("[tariffpeg]\ncrawl_delay_millis = 5000\n")
    assert caught.value.value == "crawl_delay_millis"
    assert "no such key" in caught.value.reason


def test_a_table_the_file_should_not_carry_is_refused() -> None:
    with pytest.raises(Invalid, match="carries one table"):
        read_text("[other]\nx = 1\n")


def test_a_file_that_is_not_valid_toml_is_refused() -> None:
    with pytest.raises(Invalid, match="not valid toml"):
        read_text("[tariffpeg\n")


def test_an_empty_file_leaves_the_defaults_alone() -> None:
    assert read_text("") == DEFAULTS


def test_the_section_has_to_be_a_table() -> None:
    with pytest.raises(Invalid, match="a table of settings"):
        read_text("tariffpeg = 4\n")


def test_a_value_that_the_settings_refuse_is_still_refused_from_a_file() -> None:
    with pytest.raises(Invalid, match="floor for any channel"):
        read_text("[tariffpeg]\ncrawl_delay_ms = 10\n")


def test_settings_can_be_layered_over_something_other_than_the_defaults() -> None:
    first = read_text("[tariffpeg]\ncrawl_delay_ms = 5000\n")
    second = read_text("[tariffpeg]\ndaily_request_ceiling = 50\n", first)
    assert second.crawl_delay_ms == 5000
    assert second.daily_request_ceiling == 50


def test_a_file_is_read_off_disk(tmp_path: Path) -> None:
    target = tmp_path / "tariffpeg.toml"
    target.write_text("[tariffpeg]\ncrawl_delay_ms = 5000\n", encoding="utf-8")
    assert load(target).crawl_delay_ms == 5000


def test_a_settings_file_that_is_not_there_is_refused(tmp_path: Path) -> None:
    with pytest.raises(Invalid, match="no settings file here"):
        load(tmp_path / "nothing.toml")


def test_only_the_changed_settings_come_back_when_that_is_asked_for() -> None:
    settings = read_text("[tariffpeg]\ncrawl_delay_ms = 5000\n")
    assert settings.changed_from_default() == {"crawl_delay_ms": 5000}
    assert DEFAULTS.changed_from_default() == {}


def test_the_description_marks_what_has_been_changed() -> None:
    rows = describe(read_text("[tariffpeg]\ncrawl_delay_ms = 5000\n"))
    changed = [row for row in rows if row["changed"]]
    assert len(changed) == 1
    assert changed[0]["setting"] == "crawl_delay_ms"


def test_the_description_prints_a_list_as_a_line() -> None:
    rows = describe(DEFAULTS)
    listed = [row for row in rows if row["setting"] == "inspectors"]
    assert listed[0]["value"] == "Trewin, Angove"


def test_the_holidays_read_back_as_days_the_authority_is_shut() -> None:
    settings = DEFAULTS.with_values({"holidays": ["2026-03-09", "2026-12-28"]})
    assert settings.holiday_days() == frozenset({dt.date(2026, 3, 9), dt.date(2026, 12, 28)})


def test_a_unit_that_named_no_holidays_has_none() -> None:
    assert DEFAULTS.holiday_days() == frozenset()


def test_a_holiday_written_as_something_other_than_a_date_is_refused() -> None:
    with pytest.raises(Invalid, match="written as a full date"):
        DEFAULTS.with_values({"holidays": ["Feast of St Piran"]})


def test_the_same_holiday_listed_twice_is_refused() -> None:
    with pytest.raises(Invalid, match="listed once"):
        DEFAULTS.with_values({"holidays": ["2026-03-09", "2026-03-09"]})


def test_a_holiday_list_that_is_not_a_list_is_refused() -> None:
    with pytest.raises(Invalid, match="written as a list"):
        DEFAULTS.with_values({"holidays": "2026-03-09"})


def test_a_holiday_read_out_of_toml_as_a_bare_date_is_kept() -> None:
    settings = read_text(HOLIDAY_FILE)
    assert settings.holiday_days() == frozenset({dt.date(2026, 3, 9)})
