"""Everybody who joins asks what a particular is, so the answer comes from the code."""

from __future__ import annotations

from tariffpeg.model.particulars import SPECS
from tariffpeg.tools import build_glossary
from tariffpeg.tools.document import stale


def test_the_document_on_disk_is_what_the_code_would_write() -> None:
    assert stale(build_glossary.DOCUMENT, build_glossary.text()) == ""


def test_every_particular_the_order_lists_is_in_the_glossary() -> None:
    text = build_glossary.text()
    for spec in SPECS:
        assert f"`{spec.key}`" in text
        assert spec.label in text


def test_a_particular_with_a_tolerance_carries_it() -> None:
    lines = [line for line in build_glossary.text().splitlines() if "`bed_spaces`" in line]
    assert lines[0].endswith("| 2 |")


def test_a_particular_with_no_tolerance_leaves_the_column_empty() -> None:
    lines = [line for line in build_glossary.text().splitlines() if "`lift`" in line]
    assert lines[0].endswith("|  |")


def test_every_vocabulary_has_a_heading_and_a_sentence() -> None:
    text = build_glossary.text()
    for title, _, sentence in build_glossary.VOCABULARIES:
        assert f"## {title}" in text
        assert sentence in text


def test_every_value_of_every_vocabulary_is_listed() -> None:
    text = build_glossary.text()
    for _, vocabulary, _ in build_glossary.VOCABULARIES:
        for member in vocabulary:
            assert f"`{member}`" in text


def test_the_dispositions_are_written_down_in_the_glossary() -> None:
    text = build_glossary.text()
    assert "`re-inspection`" in text
    assert "`urgent re-inspection`" in text


def test_the_document_says_what_wrote_it() -> None:
    assert "Written by build_glossary" in build_glossary.text()


def test_the_generator_writes_and_checks_the_document() -> None:
    assert build_glossary.main() == 0
