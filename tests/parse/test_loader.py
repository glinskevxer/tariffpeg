"""A profile with selector spelled wrong would register happily and find nothing."""

from __future__ import annotations

from pathlib import Path

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.parse.loader import by_channel, load, read_text

GOOD = """
[[profile]]
channel = "seaboard"
version = 2
container = "article.review"
next_page = "a.next"
prefer_structured = true

[[profile.field]]
name = "channel_review_id"
source = "attribute"
selector = "article.review"
attribute = "data-id"
required = true

[[profile.field]]
name = "body"
selector = "p.body"
required = true

[[profile.field]]
name = "score"
source = "structured"
key = "ratingValue"
required = true
"""
BARE = '[[profile]]\nchannel = "x"\nversion = 1\ncontainer = "a"\n'


def test_a_profile_reads_out_of_a_file() -> None:
    profiles = read_text(GOOD)
    assert len(profiles) == 1
    profile = profiles[0]
    assert profile.key() == "seaboard/v2"
    assert profile.container == "article.review"
    assert profile.next_page == "a.next"
    assert profile.prefer_structured


def test_the_fields_read_with_their_sources() -> None:
    profile = read_text(GOOD)[0]
    assert profile.field_names() == ("channel_review_id", "body", "score")
    assert [rule.name for rule in profile.structured_rules()] == ["score"]
    body = profile.rule("body")
    assert body is not None
    assert body.source == "text"
    assert not body.attribute


def test_an_empty_file_has_no_profiles_in_it() -> None:
    assert read_text("") == ()


def test_a_file_that_is_not_valid_toml_is_refused() -> None:
    with pytest.raises(Invalid, match="not valid toml"):
        read_text("[[profile\n")


def test_a_table_the_file_should_not_carry_is_refused() -> None:
    with pytest.raises(Invalid, match="carries one table"):
        read_text("[other]\nx = 1\n")


def test_the_profiles_have_to_be_a_list_of_tables() -> None:
    with pytest.raises(Invalid, match="list of tables"):
        read_text("profile = 4\n")


def test_the_fields_have_to_be_a_list_of_tables() -> None:
    with pytest.raises(Invalid, match="list of tables"):
        read_text(BARE + "field = 4\n")


def test_a_profile_missing_something_it_has_to_say_is_refused() -> None:
    for missing in ("channel", "version", "container"):
        text = GOOD.replace(f"{missing} =", f"x_{missing} =", 1)
        with pytest.raises(Invalid):
            read_text(text)


def test_an_unknown_key_on_a_profile_is_refused_by_name() -> None:
    text = GOOD.replace("next_page =", "nextpage =", 1)
    with pytest.raises(Invalid) as caught:
        read_text(text)
    assert caught.value.value == "nextpage"
    assert "no such key" in caught.value.reason


def test_an_unknown_key_on_a_field_is_refused_by_name() -> None:
    text = GOOD.replace("attribute =", "attr =", 1)
    with pytest.raises(Invalid, match="no such key"):
        read_text(text)


def test_a_field_that_does_not_say_which_field_it_is_is_refused() -> None:
    with pytest.raises(Invalid, match="which field it is"):
        read_text(BARE + '[[profile.field]]\nselector = "b"\n')


def test_a_profile_the_reader_would_refuse_is_still_refused_from_a_file() -> None:
    text = GOOD.replace('container = "article.review"', 'container = "article:hover"')
    with pytest.raises(Invalid, match="pseudo class is not supported"):
        read_text(text)


def test_a_channel_described_twice_in_one_file_is_refused() -> None:
    with pytest.raises(Invalid, match="described once per file"):
        read_text(GOOD + GOOD)


def test_the_profiles_can_be_looked_up_by_channel() -> None:
    found = by_channel(read_text(GOOD))
    assert sorted(found) == ["seaboard"]
    assert found["seaboard"].version == 2


def test_a_file_is_read_off_disk(tmp_path: Path) -> None:
    target = tmp_path / "profiles.toml"
    target.write_text(GOOD, encoding="utf-8")
    assert load(target)[0].channel == "seaboard"


def test_a_profile_file_that_is_not_there_is_refused(tmp_path: Path) -> None:
    with pytest.raises(Invalid, match="no profile file here"):
        load(tmp_path / "nothing.toml")
