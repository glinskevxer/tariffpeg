"""A small selector language, because extraction profiles are written in it.

This is a subset and it is meant to stay one. Every selector in a channel
profile is read by somebody in the unit who is not a web developer, and the
smaller the language is the fewer ways there are for a profile to mean something
other than what it looks like it means.

What is supported: tag names, the universal selector, ids, classes, attribute
tests, first and last child, nth of type, and the three combinators that read
left to right. What is not supported raises rather than matching nothing, which
is the difference between a profile with a typo in it and a property with no
reviews.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from tariffpeg.errors import Invalid
from tariffpeg.parse.dom import Element

QUOTE = chr(39)

_SIMPLE = re.compile(
    r"(?P<tag>\*|[a-zA-Z][\w-]*)?"
    r"(?P<rest>(?:[#.][\w-]+|\[[^\]]*\]|:[a-z-]+(?:\([^)]*\))?)*)"
)
_PIECE = re.compile(r"[#.][\w-]+|\[[^\]]*\]|:[a-z-]+(?:\([^)]*\))?")
ATTRIBUTE_OPERATORS = ("=", "~=", "^=", "$=", "*=", "|=")
"""The attribute tests a profile may use.

The regular expression below is built from this tuple rather than repeating it,
so a test added here is a test the parser accepts and nothing has to agree with
anything by hand."""

_MODIFIERS = "".join(operator[0] for operator in ATTRIBUTE_OPERATORS if len(operator) > 1)

_ATTR = re.compile(
    r"\[\s*([\w-]+)\s*(?:([" + _MODIFIERS + r"]?=)\s*"
    r"(?:\"([^\"]*)\"|" + QUOTE + r"([^" + QUOTE + r"]*)" + QUOTE + r"|([^\]]*?))\s*)?\]"
)

PSEUDO_CLASSES = ("first-child", "last-child", "only-child", "nth-of-type", "not-empty")
"""The pseudo classes a profile may use."""


@dataclass(frozen=True, slots=True)
class AttributeTest:
    """One attribute condition inside square brackets."""

    name: str
    operator: str | None
    value: str

    def matches(self, element: Element) -> bool:
        """Return whether the element satisfies this condition."""
        if not element.has(self.name):
            return False
        if self.operator is None:
            return True
        actual = element.get(self.name)
        if self.operator == "=":
            return actual == self.value
        if self.operator == "~=":
            return self.value in actual.split()
        if self.operator == "^=":
            return bool(self.value) and actual.startswith(self.value)
        if self.operator == "$=":
            return bool(self.value) and actual.endswith(self.value)
        if self.operator == "*=":
            return bool(self.value) and self.value in actual
        return actual == self.value or actual.startswith(f"{self.value}-")


@dataclass(frozen=True, slots=True)
class Simple:
    """One compound of conditions that all apply to the same element."""

    tag: str | None = None
    node_id: str | None = None
    classes: tuple[str, ...] = ()
    attributes: tuple[AttributeTest, ...] = ()
    pseudos: tuple[tuple[str, str], ...] = ()

    def matches(self, element: Element) -> bool:
        """Return whether this compound describes the element."""
        if self.tag is not None and element.tag != self.tag:
            return False
        if self.node_id is not None and element.node_id() != self.node_id:
            return False
        if any(name not in element.classes() for name in self.classes):
            return False
        if any(not test.matches(element) for test in self.attributes):
            return False
        return all(_pseudo(name, argument, element) for name, argument in self.pseudos)


@dataclass(frozen=True, slots=True)
class Step:
    """One compound and how it joins to the one on its left."""

    combinator: str
    simple: Simple


@dataclass(frozen=True, slots=True)
class Selector:
    """A whole selector, or a comma separated list of them."""

    branches: tuple[tuple[Step, ...], ...]

    def matches(self, element: Element) -> bool:
        """Return whether any branch of this selector describes the element."""
        return any(_matches_branch(branch, element) for branch in self.branches)

    def select(self, root: Element) -> tuple[Element, ...]:
        """Return the elements under the root that this selector describes."""
        return tuple(node for node in root.descendants() if self.matches(node))

    def first(self, root: Element) -> Element | None:
        """Return the first element the selector describes, or nothing."""
        for node in root.descendants():
            if self.matches(node):
                return node
        return None


def _pseudo(name: str, argument: str, element: Element) -> bool:
    parent = element.parent
    siblings = parent.elements() if parent is not None else (element,)
    if name == "first-child":
        return siblings[0] is element
    if name == "last-child":
        return siblings[-1] is element
    if name == "only-child":
        return len(siblings) == 1
    if name == "not-empty":
        return bool(element.text().strip())
    same = [node for node in siblings if node.tag == element.tag]
    try:
        wanted = int(argument)
    except ValueError:
        raise Invalid("selector", argument, "nth-of-type takes a number") from None
    return 1 <= wanted <= len(same) and same[wanted - 1] is element


def _matches_branch(branch: tuple[Step, ...], element: Element) -> bool:
    last = branch[-1]
    if not last.simple.matches(element):
        return False
    if len(branch) == 1:
        return True
    rest = branch[:-1]
    if last.combinator == ">":
        return element.parent is not None and _matches_branch(rest, element.parent)
    if last.combinator == "+":
        previous = _previous_sibling(element)
        return previous is not None and _matches_branch(rest, previous)
    return any(_matches_branch(rest, ancestor) for ancestor in element.ancestors())


def _previous_sibling(element: Element) -> Element | None:
    parent = element.parent
    if parent is None:
        return None
    previous: Element | None = None
    for node in parent.elements():
        if node is element:
            return previous
        previous = node
    return None


def _parse_attribute(piece: str) -> AttributeTest:
    match = _ATTR.fullmatch(piece)
    if match is None:
        raise Invalid("selector", piece, "this is not an attribute test")
    operator = match.group(2)
    value = match.group(3) or match.group(4) or match.group(5) or ""
    return AttributeTest(match.group(1), operator, value)


def _parse_pseudo(piece: str) -> tuple[str, str]:
    name, _, rest = piece[1:].partition("(")
    if name not in PSEUDO_CLASSES:
        raise Invalid("selector", name, "this pseudo class is not supported")
    argument = rest.rstrip(")").strip()
    if name == "nth-of-type" and not argument:
        raise Invalid("selector", piece, "nth-of-type takes a number")
    return name, argument


def _parse_simple(text: str) -> Simple:
    match = _SIMPLE.fullmatch(text)
    if match is None or not text:
        raise Invalid("selector", text, "this is not a compound this reader understands")
    tag = match.group("tag")
    node_id: str | None = None
    classes: list[str] = []
    attributes: list[AttributeTest] = []
    pseudos: list[tuple[str, str]] = []
    for piece in _PIECE.findall(match.group("rest") or ""):
        if piece.startswith("#"):
            node_id = piece[1:]
        elif piece.startswith("."):
            classes.append(piece[1:])
        elif piece.startswith("["):
            attributes.append(_parse_attribute(piece))
        else:
            pseudos.append(_parse_pseudo(piece))
    return Simple(
        None if tag in (None, "*") else tag,
        node_id,
        tuple(classes),
        tuple(attributes),
        tuple(pseudos),
    )


def _split_branch(text: str) -> list[str]:
    """Return the words of a branch, keeping brackets and quotes together.

    Splitting on a regular expression looks right until a channel serves an
    attribute value with a plus sign in it, at which point the reader decides
    the middle of a mime type is a sibling combinator.
    """
    words: list[str] = []
    current: list[str] = []
    depth = 0
    quote = ""

    def flush() -> None:
        if current:
            words.append("".join(current))
            current.clear()

    for char in text:
        if quote:
            current.append(char)
            if char == quote:
                quote = ""
            continue
        if char in (chr(34), QUOTE) and depth:
            quote = char
            current.append(char)
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth = max(0, depth - 1)
        if depth == 0 and char.isspace():
            flush()
            continue
        if depth == 0 and char in (">", "+"):
            flush()
            words.append(char)
            continue
        current.append(char)
    flush()
    return words


def _parse_branch(text: str) -> tuple[Step, ...]:
    if not text:
        raise Invalid("selector", text, "a branch of a selector cannot be blank")
    steps: list[Step] = []
    combinator = " "
    for word in _split_branch(text):
        if word in (">", "+"):
            if not steps:
                raise Invalid("selector", text, "a branch cannot start with a combinator")
            combinator = word
            continue
        steps.append(Step(combinator, _parse_simple(word)))
        combinator = " "
    if not steps:
        raise Invalid("selector", text, "a branch of a selector cannot be blank")
    if combinator != " ":
        raise Invalid("selector", text, "a branch cannot end with a combinator")
    return tuple(steps)


def _split_list(text: str) -> list[str]:
    """Return the comma separated branches, ignoring commas inside brackets."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for char in text:
        if char == "[":
            depth += 1
        elif char == "]":
            depth = max(0, depth - 1)
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    parts.append("".join(current))
    return parts


def compile_selector(text: str) -> Selector:
    """Read a selector, raising on anything this reader does not support."""
    cleaned = text.strip()
    if not cleaned:
        raise Invalid("selector", text, "a selector cannot be blank")
    return Selector(tuple(_parse_branch(part.strip()) for part in _split_list(cleaned)))
