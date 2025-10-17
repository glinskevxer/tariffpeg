"""Nothing below the command line imports the command line."""

from __future__ import annotations

from tariffpeg.tools import check_layers
from tariffpeg.tools.walk import SourceFile
from tests.tools.conftest import Planter, make_source


def source(relative: str, *imports: str) -> SourceFile:
    body = "".join(f"import {name}\n" for name in imports)
    return make_source(relative, f'"""x."""\n\n{body}')


def test_the_real_tree_only_imports_downwards() -> None:
    assert check_layers.problems() == []


def test_the_layer_of_a_module_is_read_off_its_name() -> None:
    assert check_layers.layer_of("tariffpeg.store.db") == "store"
    assert check_layers.layer_of("tariffpeg.errors") == ""
    assert check_layers.layer_of("tariffpeg") == ""


def test_a_layer_importing_one_it_is_allowed_to_reads_clean(plant: Planter) -> None:
    plant(check_layers, "source_files", [source("tariffpeg/store/x.py", "tariffpeg.model.licence")])
    assert check_layers.problems() == []


def test_the_model_importing_the_store_is_reported(plant: Planter) -> None:
    plant(check_layers, "source_files", [source("tariffpeg/model/x.py", "tariffpeg.store.db")])
    found = check_layers.problems()
    assert len(found) == 1
    assert "is in model and imports tariffpeg.store.db" in found[0]


def test_the_store_importing_the_fetcher_is_reported(plant: Planter) -> None:
    plant(check_layers, "source_files", [source("tariffpeg/store/x.py", "tariffpeg.fetch.live")])
    assert any("is in store" in problem for problem in check_layers.problems())


def test_anything_below_the_command_line_importing_it_is_reported(plant: Planter) -> None:
    plant(check_layers, "source_files", [source("tariffpeg/store/x.py", "tariffpeg.cli.main")])
    found = check_layers.problems()
    assert found == ["src/tariffpeg/store/x.py imports the command line"]


def test_the_tools_may_import_the_command_line(plant: Planter) -> None:
    plant(check_layers, "source_files", [source("tariffpeg/tools/x.py", "tariffpeg.cli.main")])
    assert check_layers.problems() == []


def test_the_command_line_may_import_anything(plant: Planter) -> None:
    plant(
        check_layers,
        "source_files",
        [source("tariffpeg/cli/x.py", "tariffpeg.store.db", "tariffpeg.report.casefile")],
    )
    assert check_layers.problems() == []


def test_the_module_that_joins_the_layers_up_may_import_anything(plant: Planter) -> None:
    plant(check_layers, "source_files", [source("tariffpeg/service.py", "tariffpeg.store.db")])
    assert check_layers.problems() == []


def test_the_base_layer_importing_a_layer_above_it_is_reported(plant: Planter) -> None:
    plant(check_layers, "source_files", [source("tariffpeg/errors.py", "tariffpeg.store.db")])
    assert any("the base layer" in problem for problem in check_layers.problems())


def test_a_module_outside_the_store_importing_sqlite_is_reported(plant: Planter) -> None:
    plant(check_layers, "source_files", [source("tariffpeg/parse/x.py", "sqlite3")])
    found = check_layers.problems()
    assert found == ["src/tariffpeg/parse/x.py imports sqlite3, which only the store may do"]


def test_the_store_may_import_sqlite(plant: Planter) -> None:
    plant(check_layers, "source_files", [source("tariffpeg/store/x.py", "sqlite3")])
    assert check_layers.problems() == []


def test_an_import_from_outside_the_package_is_left_alone(plant: Planter) -> None:
    plant(check_layers, "source_files", [source("tariffpeg/model/x.py", "datetime", "httpx")])
    assert check_layers.problems() == []


def test_every_layer_in_the_package_is_in_the_table() -> None:
    from tariffpeg.tools.walk import source_files

    layers = {found.layer for found in source_files()}
    assert layers <= set(check_layers.ALLOWED)


def test_the_check_exits_nothing_on_a_clean_tree() -> None:
    assert check_layers.main() == 0
