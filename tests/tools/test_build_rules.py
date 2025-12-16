"""The document printed when an operator asks on what basis a sentence was read."""

from __future__ import annotations

from tariffpeg.claims.pack import PACK
from tariffpeg.tools import build_rules
from tariffpeg.tools.document import stale


def test_the_document_on_disk_is_what_the_code_would_write() -> None:
    assert stale(build_rules.DOCUMENT, build_rules.text()) == ""


def test_the_document_says_which_pack_version_it_is() -> None:
    assert f"Pack version {PACK.version}" in build_rules.text()


def test_every_particular_the_pack_speaks_to_has_a_heading() -> None:
    text = build_rules.text()
    for claim_key in PACK.claim_keys():
        assert f"## {claim_key}" in text


def test_every_rule_in_the_pack_is_listed_with_its_pattern() -> None:
    text = build_rules.text()
    for rule in PACK.rules:
        assert f"`{rule.rule_id}`" in text
        # The table escapes the pipe a choice is written with, so the pattern is
        # looked for in the form the document actually prints.
        assert rule.pattern.replace("|", chr(92) + "|") in text


def test_a_rule_carries_its_weight_and_its_kind() -> None:
    lines = [line for line in build_rules.text().splitlines() if "`lift-absent`" in line]
    assert "structural" in lines[0]
    assert "denies" in lines[0]
    assert lines[0].endswith("| 5 |")


def test_a_tolerance_is_written_out_with_the_direction_it_runs() -> None:
    text = build_rules.text()
    assert "Tolerance 2, either way." in text
    assert "Tolerance 150, over only." in text


def test_the_conversion_from_minutes_to_metres_is_written_down() -> None:
    assert "80 metres a minute" in build_rules.text()


def test_the_notes_on_the_two_lift_rules_are_carried_through() -> None:
    text = build_rules.text()
    assert "`lift-absent`: the guest says the premises has none at all." in text


def test_the_document_says_what_wrote_it() -> None:
    assert "Written by build_rules" in build_rules.text()


def test_the_generator_writes_and_checks_the_document() -> None:
    assert build_rules.main() == 0
