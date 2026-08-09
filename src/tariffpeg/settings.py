"""The settings file, and what happens when it has a typo in it.

An unknown key is an error rather than something quietly ignored. The settings
that matter here change how hard the unit reads other people servers and how
much evidence it needs before it sends somebody out, and a misspelled key that
falls back to a default without saying so is the wrong failure for both.
"""

from __future__ import annotations

import datetime as dt
import tomllib
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path

from tariffpeg.errors import Invalid

SECTION = "tariffpeg"
"""The one table a settings file is allowed to carry."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Everything the unit can change without a release."""

    database: str = "tariffpeg.sqlite3"
    contact: str = "standards@example-authority.test"
    agent_name: str = "tariffpeg-harvester"
    crawl_delay_ms: int = 2000
    daily_request_ceiling: int = 300
    max_pages_per_property: int = 8
    lookback_months: int = 24
    minimum_channels: int = 2
    weekly_capacity: int = 4
    inspectors: tuple[str, ...] = ("Trewin", "Angove")
    holidays: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if "@" not in self.contact:
            raise Invalid(
                "contact", self.contact, "the contact is an address a channel can write to"
            )
        if not self.agent_name.strip():
            raise Invalid("agent_name", self.agent_name, "the agent string needs a name in it")
        for name in ("crawl_delay_ms", "daily_request_ceiling", "max_pages_per_property"):
            if getattr(self, name) < 1:
                raise Invalid(name, getattr(self, name), "this setting is one or more")
        if self.crawl_delay_ms < 250:
            raise Invalid("crawl_delay_ms", self.crawl_delay_ms, "the floor for any channel is 250")
        if self.lookback_months < 1:
            raise Invalid("lookback_months", self.lookback_months, "a lookback is a month or more")
        if self.minimum_channels < 1:
            raise Invalid("minimum_channels", self.minimum_channels, "a sample needs one channel")
        if self.weekly_capacity < 1:
            raise Invalid(
                "weekly_capacity", self.weekly_capacity, "a diary holds one visit or more"
            )
        if not self.inspectors:
            raise Invalid("inspectors", 0, "there has to be somebody to send")
        if len(set(self.inspectors)) != len(self.inspectors):
            raise Invalid("inspectors", len(self.inspectors), "an inspector is named once")
        for written in self.holidays:
            try:
                dt.date.fromisoformat(written)
            except ValueError:
                raise Invalid("holidays", written, "a holiday is written as a full date") from None
        if len(set(self.holidays)) != len(self.holidays):
            raise Invalid("holidays", len(self.holidays), "a holiday is listed once")

    def holiday_days(self) -> frozenset[dt.date]:
        """Return the days nobody travels and no reply clock runs.

        These are not weekends. Weekends are arithmetic and this package knows
        about them already. These are the days the authority is shut, which are
        local, move every year, and are the reason a reply deadline computed
        from a national calendar is wrong here.
        """
        return frozenset(dt.date.fromisoformat(written) for written in self.holidays)

    @property
    def user_agent(self) -> str:
        """Return the agent string the fetcher sends."""
        return f"{self.agent_name} ({self.contact})"

    def with_values(self, values: Mapping[str, object]) -> Settings:
        """Return a copy with some settings changed, refusing unknown keys."""
        known = {field.name for field in fields(self)}
        unknown = sorted(set(values) - known)
        if unknown:
            raise Invalid("settings", unknown[0], "the settings file has no such key")
        typed = dict(values)
        for key in ("inspectors", "holidays"):
            if key not in typed:
                continue
            listed = typed[key]
            if not isinstance(listed, list | tuple):
                raise Invalid(key, listed, f"the {key} are written as a list")
            typed[key] = tuple(
                item.isoformat() if isinstance(item, dt.date) else str(item) for item in listed
            )
        return replace(self, **typed)  # type: ignore[arg-type]

    def as_dict(self) -> dict[str, object]:
        """Return the settings as a plain mapping."""
        return asdict(self)

    def changed_from_default(self) -> dict[str, object]:
        """Return only the settings that differ from what ships."""
        base = Settings().as_dict()
        return {key: value for key, value in self.as_dict().items() if base[key] != value}


DEFAULTS = Settings()
"""What the unit runs with when there is no settings file."""


def read_text(text: str, base: Settings | None = None) -> Settings:
    """Read settings out of the text of a file."""
    try:
        loaded = tomllib.loads(text)
    except tomllib.TOMLDecodeError as err:
        raise Invalid("settings", str(err), "the settings file is not valid toml") from None
    extra = sorted(set(loaded) - {SECTION})
    if extra:
        raise Invalid("settings", extra[0], f"a settings file carries one table, {SECTION}")
    values = loaded.get(SECTION, {})
    if not isinstance(values, dict):
        raise Invalid("settings", SECTION, "the section is a table of settings")
    return (base or DEFAULTS).with_values(values)


def load(path: str | Path, base: Settings | None = None) -> Settings:
    """Read a settings file off disk."""
    target = Path(path)
    if not target.exists():
        raise Invalid("settings", str(target), "there is no settings file here")
    return read_text(target.read_text(encoding="utf-8"), base)


def describe(settings: Settings) -> tuple[dict[str, object], ...]:
    """Return one row per setting, for the table the CLI prints."""
    base = Settings().as_dict()
    rows: list[dict[str, object]] = []
    for key, value in settings.as_dict().items():
        shown = ", ".join(value) if isinstance(value, tuple) else value
        rows.append({"setting": key, "value": shown, "changed": base[key] != value})
    return tuple(rows)
