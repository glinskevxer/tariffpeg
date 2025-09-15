"""Reading extraction profiles out of a file.

Profiles change when a channel changes its templates, which is far more often
than this package is released. So they live in a file the unit edits, and the
file is read strictly: an unknown key is a refusal, because a profile with
selector spelled wrong would otherwise register happily and then find nothing.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tariffpeg.errors import Invalid
from tariffpeg.parse.profile import FieldRule, Profile

PROFILE_KEYS = frozenset(
    {"channel", "version", "container", "next_page", "prefer_structured", "field"}
)
FIELD_KEYS = frozenset({"name", "source", "selector", "attribute", "key", "required"})


def _check_keys(where: str, given: Mapping[str, Any], allowed: frozenset[str]) -> None:
    unknown = sorted(set(given) - allowed)
    if unknown:
        raise Invalid(where, unknown[0], "a profile file has no such key")


def _field(raw: Mapping[str, Any]) -> FieldRule:
    _check_keys("field", raw, FIELD_KEYS)
    if "name" not in raw:
        raise Invalid("field", "name", "every field says which field it is")
    return FieldRule(
        name=str(raw["name"]),
        source=str(raw.get("source", "text")),
        selector=str(raw.get("selector", "")),
        attribute=str(raw.get("attribute", "")),
        key=str(raw.get("key", "")),
        required=bool(raw.get("required", False)),
    )


def _profile(raw: Mapping[str, Any]) -> Profile:
    _check_keys("profile", raw, PROFILE_KEYS)
    for wanted in ("channel", "version", "container"):
        if wanted not in raw:
            raise Invalid("profile", wanted, "every profile says this")
    fields = raw.get("field", [])
    if not isinstance(fields, list):
        raise Invalid("field", type(fields).__name__, "the fields are written as a list of tables")
    return Profile(
        channel=str(raw["channel"]),
        version=int(raw["version"]),
        container=str(raw["container"]),
        fields=tuple(_field(entry) for entry in fields),
        next_page=str(raw.get("next_page", "")),
        prefer_structured=bool(raw.get("prefer_structured", False)),
    )


def read_text(text: str) -> tuple[Profile, ...]:
    """Read every profile in the text of a file."""
    try:
        loaded = tomllib.loads(text)
    except tomllib.TOMLDecodeError as err:
        raise Invalid("profiles", str(err), "the profile file is not valid toml") from None
    extra = sorted(set(loaded) - {"profile"})
    if extra:
        raise Invalid("profiles", extra[0], "a profile file carries one table, profile")
    raw = loaded.get("profile", [])
    if not isinstance(raw, list):
        raise Invalid("profile", type(raw).__name__, "the profiles are written as a list of tables")
    profiles = tuple(_profile(entry) for entry in raw)
    seen: set[str] = set()
    for profile in profiles:
        if profile.channel in seen:
            raise Invalid("profile", profile.channel, "a channel is described once per file")
        seen.add(profile.channel)
    return profiles


def load(path: str | Path) -> tuple[Profile, ...]:
    """Read a profile file off disk."""
    target = Path(path)
    if not target.exists():
        raise Invalid("profiles", str(target), "there is no profile file here")
    return read_text(target.read_text(encoding="utf-8"))


def by_channel(profiles: Sequence[Profile]) -> dict[str, Profile]:
    """Return the profiles indexed by the channel they read."""
    return {profile.channel: profile for profile in profiles}
