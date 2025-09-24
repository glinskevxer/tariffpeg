"""Rerunning the pipeline against exactly what was fetched on the day."""

from __future__ import annotations

from pathlib import Path

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.fetch.bundle import INDEX, load
from tariffpeg.fetch.transport import Request

AGENT = "tariffpeg-harvester (standards@example-authority.test)"
INDEX_TEXT = """
[[page]]
url = "https://seaboard.example/robots.txt"
body = "robots.txt"
content_type = "text/plain"

[[page]]
url = "https://seaboard.example/p/1"
body = "page-one.html"
etag = "abc"
"""


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    (tmp_path / INDEX).write_text(INDEX_TEXT, encoding="utf-8")
    (tmp_path / "robots.txt").write_text("User-agent: *\n", encoding="utf-8")
    (tmp_path / "page-one.html").write_text("<html>one</html>", encoding="utf-8")
    return tmp_path


def test_a_bundle_answers_the_urls_it_recorded(bundle: Path) -> None:
    transport = load(bundle)
    reply = transport.get(Request("https://seaboard.example/p/1", AGENT))
    assert reply.status == 200
    assert reply.text() == "<html>one</html>"


def test_the_recorded_headers_come_back(bundle: Path) -> None:
    transport = load(bundle)
    robots = transport.get(Request("https://seaboard.example/robots.txt", AGENT))
    assert robots.headers.get("content-type") == "text/plain"
    page = transport.get(Request("https://seaboard.example/p/1", AGENT))
    assert page.headers.get("etag") == "abc"


def test_a_url_the_bundle_never_recorded_is_a_failure(bundle: Path) -> None:
    from tariffpeg.errors import FetchFailed

    with pytest.raises(FetchFailed):
        load(bundle).get(Request("https://seaboard.example/p/9", AGENT))


def test_a_status_can_be_recorded_alongside_the_body(tmp_path: Path) -> None:
    (tmp_path / INDEX).write_text(
        '[[page]]\nurl = "https://x.test/a"\nbody = "gone.html"\nstatus = 404\n', encoding="utf-8"
    )
    (tmp_path / "gone.html").write_text("", encoding="utf-8")
    assert load(tmp_path).get(Request("https://x.test/a", AGENT)).missing


def test_a_directory_with_no_index_is_refused(tmp_path: Path) -> None:
    with pytest.raises(Invalid, match="an index of the pages"):
        load(tmp_path)


def test_an_index_that_is_not_valid_toml_is_refused(tmp_path: Path) -> None:
    (tmp_path / INDEX).write_text("[[page\n", encoding="utf-8")
    with pytest.raises(Invalid, match="not valid toml"):
        load(tmp_path)


def test_a_table_the_index_should_not_carry_is_refused(tmp_path: Path) -> None:
    (tmp_path / INDEX).write_text("[other]\nx = 1\n", encoding="utf-8")
    with pytest.raises(Invalid, match="carries one table"):
        load(tmp_path)


def test_the_pages_have_to_be_a_list_of_tables(tmp_path: Path) -> None:
    (tmp_path / INDEX).write_text("page = 4\n", encoding="utf-8")
    with pytest.raises(Invalid, match="list of tables"):
        load(tmp_path)


def test_an_unknown_key_in_the_index_is_refused(tmp_path: Path) -> None:
    (tmp_path / INDEX).write_text(
        '[[page]]\nurl = "https://x.test/a"\nbody = "a.html"\nmime = "x"\n', encoding="utf-8"
    )
    (tmp_path / "a.html").write_text("", encoding="utf-8")
    with pytest.raises(Invalid, match="no such key"):
        load(tmp_path)


def test_a_page_that_does_not_say_where_its_body_is_is_refused(tmp_path: Path) -> None:
    (tmp_path / INDEX).write_text('[[page]]\nurl = "https://x.test/a"\n', encoding="utf-8")
    with pytest.raises(Invalid, match="says this"):
        load(tmp_path)


def test_an_index_naming_a_file_that_is_not_there_is_refused(tmp_path: Path) -> None:
    (tmp_path / INDEX).write_text(
        '[[page]]\nurl = "https://x.test/a"\nbody = "missing.html"\n', encoding="utf-8"
    )
    with pytest.raises(Invalid, match="not there"):
        load(tmp_path)


def test_an_empty_bundle_answers_nothing(tmp_path: Path) -> None:
    (tmp_path / INDEX).write_text("", encoding="utf-8")
    assert load(tmp_path).known() == ()
