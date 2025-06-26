"""A small pattern language for reading assertions out of review text.

Regular expressions were tried first and abandoned. The rules are written and
argued over by people in the unit who have to be able to read them back a year
later in a hearing bundle, and a rule that reads

    (there is no|there was no|they have no) ... lift

is a rule an inspector can check. The same thing written as a regular
expression is not.

Five kinds of term and no more. Literal words, a choice between phrases, an
optional word, a gap of a few words, and a number that gets captured.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from tariffpeg.errors import Invalid

GAP_WORDS = 4
"""How many words a gap will jump. Wider than this and rules start matching
across the sentence boundary into whatever the guest said next."""

_WORD = re.compile(r"[a-z0-9]+")


def tokens_of(text: str) -> tuple[str, ...]:
    """Return the words of a piece of text, lowercased and stripped of punctuation."""
    return tuple(_WORD.findall(text.lower()))


@dataclass(frozen=True, slots=True)
class Literal:
    """One or more words that have to appear in order."""

    words: tuple[str, ...]

    def match(self, tokens: tuple[str, ...], at: int) -> Iterator[tuple[int, tuple[int, ...]]]:
        """Yield where this term could end, starting from a position."""
        end = at + len(self.words)
        if tokens[at:end] == self.words:
            yield end, ()


@dataclass(frozen=True, slots=True)
class Choice:
    """A choice between phrases, any one of which satisfies the term."""

    options: tuple[tuple[str, ...], ...]

    def match(self, tokens: tuple[str, ...], at: int) -> Iterator[tuple[int, tuple[int, ...]]]:
        """Yield every position this choice could end at."""
        seen: set[int] = set()
        for option in self.options:
            end = at + len(option)
            if tokens[at:end] == option and end not in seen:
                seen.add(end)
                yield end, ()


@dataclass(frozen=True, slots=True)
class Maybe:
    """A word that may or may not be there."""

    word: str

    def match(self, tokens: tuple[str, ...], at: int) -> Iterator[tuple[int, tuple[int, ...]]]:
        """Yield the position with the word taken and the position without it."""
        if at < len(tokens) and tokens[at] == self.word:
            yield at + 1, ()
        yield at, ()


@dataclass(frozen=True, slots=True)
class Gap:
    """A run of words the rule does not care about."""

    width: int = GAP_WORDS

    def match(self, tokens: tuple[str, ...], at: int) -> Iterator[tuple[int, tuple[int, ...]]]:
        """Yield every position within the gap, nearest first."""
        for step in range(self.width + 1):
            if at + step <= len(tokens):
                yield at + step, ()


@dataclass(frozen=True, slots=True)
class Number:
    """A number, which is captured so a rule can compare it to a particular."""

    def match(self, tokens: tuple[str, ...], at: int) -> Iterator[tuple[int, tuple[int, ...]]]:
        """Yield the position after a number, capturing its value."""
        if at < len(tokens) and tokens[at].isdigit():
            yield at + 1, (int(tokens[at]),)


Term = Literal | Choice | Maybe | Gap | Number


@dataclass(frozen=True, slots=True)
class Match:
    """Where a pattern matched and what it captured."""

    start: int
    end: int
    numbers: tuple[int, ...] = ()

    def span(self, tokens: tuple[str, ...]) -> str:
        """Return the words the pattern matched, joined back up."""
        return " ".join(tokens[self.start : self.end])


@dataclass(frozen=True, slots=True)
class Pattern:
    """A compiled rule pattern."""

    source: str
    terms: tuple[Term, ...]

    def find(self, text: str) -> Match | None:
        """Return the first place this pattern matches, or nothing."""
        tokens = tokens_of(text)
        for start in range(len(tokens) + 1):
            for end, numbers in _walk(self.terms, tokens, start):
                return Match(start, end, numbers)
        return None

    def matches(self, text: str) -> bool:
        """Return whether this pattern matches anywhere in the text."""
        return self.find(text) is not None

    def find_all(self, text: str) -> tuple[Match, ...]:
        """Return every place this pattern matches, without overlapping itself."""
        tokens = tokens_of(text)
        found: list[Match] = []
        start = 0
        while start <= len(tokens):
            hit: Match | None = None
            for end, numbers in _walk(self.terms, tokens, start):
                hit = Match(start, end, numbers)
                break
            if hit is not None and hit.end > hit.start:
                found.append(hit)
                start = hit.end
                continue
            start += 1
        return tuple(found)


def _walk(
    terms: tuple[Term, ...], tokens: tuple[str, ...], at: int
) -> Iterator[tuple[int, tuple[int, ...]]]:
    if not terms:
        yield at, ()
        return
    head, rest = terms[0], terms[1:]
    for end, captured in head.match(tokens, at):
        for final, more in _walk(rest, tokens, end):
            yield final, captured + more


def _split_terms(source: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for char in source:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise Invalid("pattern", source, "there is a closing bracket with no opening one")
        if char.isspace() and depth == 0:
            if current:
                parts.append("".join(current))
                current = []
            continue
        current.append(char)
    if depth:
        raise Invalid("pattern", source, "there is an opening bracket with no closing one")
    if current:
        parts.append("".join(current))
    return parts


def compile_pattern(source: str) -> Pattern:
    """Read a rule pattern, raising on anything the reader does not understand."""
    cleaned = " ".join(source.split())
    if not cleaned:
        raise Invalid("pattern", source, "a pattern cannot be blank")
    terms: list[Term] = []
    for part in _split_terms(cleaned):
        terms.append(_term(part))
    return Pattern(cleaned, tuple(terms))


def _term(part: str) -> Term:
    if part == "...":
        return Gap()
    if part == "#":
        return Number()
    if part.startswith("(") and part.endswith(")"):
        options = tuple(tokens_of(option) for option in part[1:-1].split("|") if tokens_of(option))
        if len(options) < 2:
            raise Invalid("pattern", part, "a choice needs at least two options in it")
        return Choice(options)
    if part.endswith("?"):
        words = tokens_of(part[:-1])
        if len(words) != 1:
            raise Invalid("pattern", part, "only a single word can be made optional")
        return Maybe(words[0])
    words = tokens_of(part)
    if not words:
        raise Invalid("pattern", part, "this term has no words in it")
    return Literal(words)
