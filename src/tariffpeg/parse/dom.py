"""Building a tree out of tokens, closing what the page forgot to close.

Real pages leave paragraphs and list items open. A tree builder that waits for
the closing tag ends up nesting every review inside the one before it, which
looks like one enormous review rather than forty. The closing rules below are
the small subset of the real ones that the channels we read actually need.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tariffpeg.parse.tokens import EndTag, StartTag, Text, Token, tokenize

BLOCK_AFTER_P = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "div",
        "dl",
        "fieldset",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "ul",
    }
)
"""Opening one of these closes an open paragraph."""

CLOSED_BY: dict[str, frozenset[str]] = {
    "p": BLOCK_AFTER_P,
    "li": frozenset({"li"}),
    "dt": frozenset({"dt", "dd"}),
    "dd": frozenset({"dt", "dd"}),
    "option": frozenset({"option", "optgroup"}),
    "optgroup": frozenset({"optgroup"}),
    "tr": frozenset({"tr", "tbody", "tfoot", "thead"}),
    "td": frozenset({"td", "th", "tr", "tbody", "tfoot"}),
    "th": frozenset({"td", "th", "tr", "tbody", "tfoot"}),
    "thead": frozenset({"tbody", "tfoot"}),
    "tbody": frozenset({"tbody", "tfoot"}),
}
"""Which open tag is closed by which newly opened one."""


@dataclass(slots=True)
class TextNode:
    """A run of text hanging off an element."""

    data: str
    parent: Element | None = field(default=None, compare=False, repr=False)

    def text(self) -> str:
        """Return the run itself."""
        return self.data


@dataclass(slots=True)
class Element:
    """One tag, its attributes and what is inside it."""

    tag: str
    attrs: tuple[tuple[str, str], ...] = ()
    children: list[Node] = field(default_factory=list)
    parent: Element | None = field(default=None, compare=False, repr=False)

    def get(self, name: str, default: str = "") -> str:
        """Return an attribute value, or the default."""
        for key, value in self.attrs:
            if key == name:
                return value
        return default

    def has(self, name: str) -> bool:
        """Return whether the element carries this attribute."""
        return any(key == name for key, _ in self.attrs)

    def classes(self) -> tuple[str, ...]:
        """Return the class names on the element."""
        return tuple(self.get("class").split())

    def node_id(self) -> str:
        """Return the id attribute, which is empty when there is none."""
        return self.get("id")

    def append(self, child: Node) -> None:
        """Add a child and point it back at this element."""
        child.parent = self
        self.children.append(child)

    def elements(self) -> tuple[Element, ...]:
        """Return the child elements, skipping text."""
        return tuple(child for child in self.children if isinstance(child, Element))

    def descendants(self) -> list[Element]:
        """Return every element below this one, in document order."""
        found: list[Element] = []
        for child in self.elements():
            found.append(child)
            found.extend(child.descendants())
        return found

    def ancestors(self) -> list[Element]:
        """Return the elements above this one, nearest first."""
        found: list[Element] = []
        at = self.parent
        while at is not None:
            found.append(at)
            at = at.parent
        return found

    def depth(self) -> int:
        """Return how far below the root this element sits."""
        return len(self.ancestors())

    def text(self, separator: str = "") -> str:
        """Return the text under this element, joined and stripped."""
        parts: list[str] = []
        for child in self.children:
            if isinstance(child, TextNode):
                parts.append(child.data)
            else:
                parts.append(child.text(separator))
        return separator.join(part for part in parts if part).strip()

    def find_all(self, tag: str) -> tuple[Element, ...]:
        """Return every descendant with this tag name."""
        return tuple(node for node in self.descendants() if node.tag == tag)

    def find(self, tag: str) -> Element | None:
        """Return the first descendant with this tag name, or nothing."""
        for node in self.descendants():
            if node.tag == tag:
                return node
        return None


Node = Element | TextNode


def build(tokens: list[Token]) -> Element:
    """Build a tree from tokens, under a root that is never in the page."""
    root = Element("[document]")
    open_stack: list[Element] = [root]
    for token in tokens:
        current = open_stack[-1]
        if isinstance(token, Text):
            if token.data:
                current.append(TextNode(token.data))
        elif isinstance(token, StartTag):
            while len(open_stack) > 1 and token.name in CLOSED_BY.get(open_stack[-1].tag, ()):
                open_stack.pop()
            element = Element(token.name, token.attrs)
            open_stack[-1].append(element)
            if not token.self_closing:
                open_stack.append(element)
        elif isinstance(token, EndTag):
            for index in range(len(open_stack) - 1, 0, -1):
                if open_stack[index].tag == token.name:
                    del open_stack[index:]
                    break
    return root


def parse(source: str) -> Element:
    """Tokenize a page and build its tree."""
    return build(tokenize(source))
