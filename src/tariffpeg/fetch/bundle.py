"""Reading a recorded bundle of pages off disk.

An evidence bundle is a directory of the pages that were served and an index
saying which url each one came from. Handing that to the harvest instead of a
live transport reruns the whole pipeline against exactly what was fetched on the
day, which is how a disputed case file gets answered.

It is also how the command line is tested. Nothing in this package reaches the
network unless somebody asks it to.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from tariffpeg.errors import Invalid
from tariffpeg.fetch.replay import ReplayTransport

INDEX = "pages.toml"
"""What the index inside a bundle directory is called."""

PAGE_KEYS = frozenset({"url", "body", "status", "content_type", "etag"})


def _page(raw: dict[str, Any], root: Path, transport: ReplayTransport) -> None:
    unknown = sorted(set(raw) - PAGE_KEYS)
    if unknown:
        raise Invalid("page", unknown[0], "a bundle index has no such key")
    for wanted in ("url", "body"):
        if wanted not in raw:
            raise Invalid("page", wanted, "every page in a bundle says this")
    target = root / str(raw["body"])
    if not target.exists():
        raise Invalid("body", str(target), "the bundle index names a file that is not there")
    headers = {"Content-Type": str(raw.get("content_type", "text/html; charset=utf-8"))}
    if raw.get("etag"):
        headers["ETag"] = str(raw["etag"])
    transport.add(
        url=str(raw["url"]),
        body=target.read_bytes(),
        status=int(raw.get("status", 200)),
        headers=headers,
    )


def load(directory: str | Path) -> ReplayTransport:
    """Return a transport that answers out of a recorded bundle."""
    root = Path(directory)
    index = root / INDEX
    if not index.exists():
        raise Invalid("bundle", str(index), "a bundle carries an index of the pages in it")
    try:
        loaded = tomllib.loads(index.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as err:
        raise Invalid("bundle", str(err), "the bundle index is not valid toml") from None
    extra = sorted(set(loaded) - {"page"})
    if extra:
        raise Invalid("bundle", extra[0], "a bundle index carries one table, page")
    pages = loaded.get("page", [])
    if not isinstance(pages, list):
        raise Invalid("page", type(pages).__name__, "the pages are written as a list of tables")
    transport = ReplayTransport()
    for raw in pages:
        _page(raw, root, transport)
    return transport
