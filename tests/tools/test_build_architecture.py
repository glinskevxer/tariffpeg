"""A drawing on somebody wall should never be the only description of the shape."""

from __future__ import annotations

from tariffpeg.tools import build_architecture
from tariffpeg.tools.check_layers import ALLOWED
from tariffpeg.tools.document import stale


def test_the_document_on_disk_is_what_the_code_would_write() -> None:
    assert stale(build_architecture.DOCUMENT, build_architecture.text()) == ""


def test_every_layer_in_the_table_has_a_sentence_about_it() -> None:
    for layer in ALLOWED:
        assert layer in build_architecture.SENTENCES


def test_every_layer_appears_in_the_document() -> None:
    text = build_architecture.text()
    for layer in ALLOWED:
        assert (layer or "(base)") in text


def test_a_layer_that_may_import_anything_says_so() -> None:
    lines = [line for line in build_architecture.text().splitlines() if line.startswith("| cli ")]
    assert lines[0].endswith("| anything |")


def test_a_layer_with_a_list_carries_it() -> None:
    lines = [line for line in build_architecture.text().splitlines() if line.startswith("| store ")]
    assert "model" in lines[0]
    assert "(base)" in lines[0]


def test_the_modules_that_join_the_layers_up_are_named() -> None:
    assert "`tariffpeg.service`" in build_architecture.text()


def test_the_modules_in_each_layer_are_listed() -> None:
    text = build_architecture.text()
    assert "- `tariffpeg.store.db`" in text
    assert "- `tariffpeg.errors`" in text


def test_a_package_init_is_not_listed_as_a_module() -> None:
    found = build_architecture.modules_by_layer()
    assert all(not name.endswith(".__init__") for names in found.values() for name in names)


def test_the_base_layer_holds_the_modules_with_no_subpackage() -> None:
    found = build_architecture.modules_by_layer()
    assert "tariffpeg.errors" in found[""]
    assert "tariffpeg.service" in found[""]


def test_the_document_names_the_check_that_enforces_it() -> None:
    assert "check_layers" in build_architecture.text()


def test_the_generator_writes_and_checks_the_document() -> None:
    assert build_architecture.main() == 0
