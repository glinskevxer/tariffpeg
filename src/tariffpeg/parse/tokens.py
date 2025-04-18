"""Breaking a served page into tags and text.

Channels serve markup that no validator would accept. Unquoted attributes,
attributes with no value, tags that are never closed, a stray less than sign in
a review body where a guest typed one. None of that is an error here. The
tokenizer is tolerant on purpose and the tolerance is the part that is tested,
because the day a channel changes its templates is the day this has to keep
working or say clearly that it could not.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

RAW_TEXT_TAGS = frozenset({"script", "style", "textarea", "title"})
"""Tags whose contents are not markup and are not scanned for tags."""

VOID_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "track",
        "wbr",
    }
)
"""Tags that never have a closing partner, whatever the page writes."""

_TAG_NAME = re.compile(r"[a-zA-Z][^\s/>]*")
_ATTR = re.compile(
    r"\s*([^\s/>=]+)"
    r"(?:\s*=\s*(?:\"([^\"]*)\"|" + chr(39) + r"([^" + chr(39) + r"]*)" + chr(39) + r"|([^\s>]*)))?"
)


@dataclass(frozen=True, slots=True)
class Text:
    """A run of character data between tags."""

    data: str

    def is_blank(self) -> bool:
        """Return whether this run is nothing but whitespace."""
        return not self.data.strip()


@dataclass(frozen=True, slots=True)
class Comment:
    """A comment. Kept because some channels put their review ids in one."""

    data: str


@dataclass(frozen=True, slots=True)
class Doctype:
    """The doctype line, kept so a page can be identified later."""

    data: str


@dataclass(frozen=True, slots=True)
class StartTag:
    """An opening tag and the attributes on it."""

    name: str
    attrs: tuple[tuple[str, str], ...] = ()
    self_closing: bool = False

    def get(self, name: str, default: str = "") -> str:
        """Return an attribute value, or the default if the tag has none.

        A repeated attribute keeps the first value, which is what browsers do
        and therefore what the channel saw when it checked its own page.
        """
        for key, value in self.attrs:
            if key == name:
                return value
        return default

    def has(self, name: str) -> bool:
        """Return whether the tag carries this attribute at all."""
        return any(key == name for key, _ in self.attrs)

    def classes(self) -> tuple[str, ...]:
        """Return the class names on the tag, in the order they are written."""
        return tuple(self.get("class").split())


@dataclass(frozen=True, slots=True)
class EndTag:
    """A closing tag."""

    name: str


Token = Text | Comment | Doctype | StartTag | EndTag


@dataclass(slots=True)
class Tokenizer:
    """Reads a page once, from the front, and yields what it finds."""

    source: str
    position: int = field(default=0)

    def tokens(self) -> list[Token]:
        """Return every token in the page, in order.

        Runs of text are joined. A guest who typed a less than sign produces two
        runs where the page has one, and a consumer that has to know that is a
        consumer with a bug waiting in it.
        """
        return _join_text(self._scan())

    def _scan(self) -> list[Token]:
        found: list[Token] = []
        while self.position < len(self.source):
            nxt = self.source.find("<", self.position)
            if nxt == -1:
                found.append(Text(html.unescape(self.source[self.position :])))
                break
            if nxt > self.position:
                found.append(Text(html.unescape(self.source[self.position : nxt])))
                self.position = nxt
            token = self._markup()
            if token is None:
                found.append(Text("<"))
                self.position += 1
                continue
            found.append(token)
            if isinstance(token, StartTag) and token.name in RAW_TEXT_TAGS:
                found.extend(self._raw_text(token.name))
        return found

    def _markup(self) -> Token | None:
        rest = self.source[self.position :]
        if rest.startswith("<!--"):
            end = self.source.find("-->", self.position + 4)
            if end == -1:
                data = self.source[self.position + 4 :]
                self.position = len(self.source)
                return Comment(data)
            data = self.source[self.position + 4 : end]
            self.position = end + 3
            return Comment(data)
        if rest.startswith("<!"):
            end = self.source.find(">", self.position)
            end = len(self.source) if end == -1 else end
            data = self.source[self.position + 2 : end].strip()
            self.position = end + 1
            return Doctype(data)
        if rest.startswith("</"):
            match = _TAG_NAME.match(self.source, self.position + 2)
            if match is None:
                return None
            end = self.source.find(">", match.end())
            self.position = len(self.source) if end == -1 else end + 1
            return EndTag(match.group(0).lower())
        match = _TAG_NAME.match(self.source, self.position + 1)
        if match is None:
            return None
        name = match.group(0).lower()
        attrs, end = self._attributes(match.end())
        self_closing = self.source[max(0, end - 2) : end].rstrip(">").endswith("/")
        self.position = end
        return StartTag(name, attrs, self_closing or name in VOID_TAGS)

    def _attributes(self, start: int) -> tuple[tuple[tuple[str, str], ...], int]:
        attrs: list[tuple[str, str]] = []
        at = start
        while at < len(self.source):
            if self.source[at] == ">":
                return tuple(attrs), at + 1
            if self.source[at] == "/" and self.source[at : at + 2] == "/>":
                return tuple(attrs), at + 2
            match = _ATTR.match(self.source, at)
            if match is None or match.end() == at:
                at += 1
                continue
            name = match.group(1).lower()
            raw = match.group(2) or match.group(3) or match.group(4) or ""
            attrs.append((name, html.unescape(raw)))
            at = match.end()
        return tuple(attrs), len(self.source)

    def _raw_text(self, name: str) -> list[Token]:
        closer = f"</{name}"
        end = self.source.lower().find(closer, self.position)
        if end == -1:
            data = self.source[self.position :]
            self.position = len(self.source)
            return [Text(data)] if data else []
        data = self.source[self.position : end]
        after = self.source.find(">", end)
        self.position = len(self.source) if after == -1 else after + 1
        found: list[Token] = []
        if data:
            found.append(Text(data))
        found.append(EndTag(name))
        return found


def _join_text(found: list[Token]) -> list[Token]:
    """Return the tokens with neighbouring runs of text joined into one."""
    joined: list[Token] = []
    for token in found:
        if isinstance(token, Text) and joined and isinstance(joined[-1], Text):
            joined[-1] = Text(joined[-1].data + token.data)
            continue
        joined.append(token)
    return joined


def tokenize(source: str) -> list[Token]:
    """Return the tokens in a page."""
    return Tokenizer(source).tokens()
