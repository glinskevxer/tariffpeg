"""Reading a channel's robots file and doing what it says.

The unit has a written agreement with every channel it reads, and the robots
file is the channel's side of that agreement restated in public. Where the two
disagree the stricter one wins, which is handled on the policy. What is handled
here is reading the file correctly, and correctly means the way the standard
says rather than the way that is easy.

Two things trip people up and both are implemented here. The rule that wins is
the longest matching one and not the first one, and a group with no rules in it
still counts as a group, so a channel can silence a crawler by naming it and
saying nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_BYTES = 512 * 1024
"""Past this the file is treated as unparseable. The standard suggests half a
megabyte and no channel we read comes near it."""


@dataclass(frozen=True, slots=True)
class Rule:
    """One allow or disallow line, with the path pattern it carries."""

    allow: bool
    pattern: str

    @property
    def specificity(self) -> int:
        """Return how specific this rule is, which is how long its pattern is."""
        return len(self.pattern)

    def matches(self, path: str) -> bool:
        """Return whether this rule's pattern covers the path."""
        return _match(self.pattern, path)


@dataclass(frozen=True, slots=True)
class Group:
    """One block of rules and the agents it applies to."""

    agents: tuple[str, ...]
    rules: tuple[Rule, ...] = ()
    crawl_delay_ms: int | None = None

    def best_rule(self, path: str) -> Rule | None:
        """Return the rule that decides this path, or ``None`` if none match.

        The longest matching pattern wins. Where two match at the same length
        the allow wins, which is what the standard says and is also the reading
        that keeps a channel's own exception working.
        """
        best: Rule | None = None
        for rule in self.rules:
            if not rule.matches(path):
                continue
            if (
                best is None
                or rule.specificity > best.specificity
                or rule.specificity == best.specificity
                and rule.allow
                and not best.allow
            ):
                best = rule
        return best

    def allows(self, path: str) -> bool:
        """Return whether this group lets a crawler have the path."""
        rule = self.best_rule(path)
        return True if rule is None else rule.allow


@dataclass(frozen=True, slots=True)
class Robots:
    """A parsed robots file."""

    groups: tuple[Group, ...] = ()
    sitemaps: tuple[str, ...] = ()
    unparseable: bool = False
    source: str = field(default="", compare=False)

    def group_for(self, agent: str) -> Group | None:
        """Return the group that applies to an agent, or ``None``.

        A named group beats the catch all, and the longest name that matches
        beats a shorter one. Nothing here falls back to the catch all once a
        named group has matched, because that is how a channel narrows a rule.
        """
        wanted = agent.lower()
        best: Group | None = None
        best_length = -1
        catch_all: Group | None = None
        for group in self.groups:
            for token in group.agents:
                if token == "*":
                    if catch_all is None:
                        catch_all = group
                    continue
                if wanted.startswith(token) and len(token) > best_length:
                    best = group
                    best_length = len(token)
        return best if best is not None else catch_all

    def allows(self, agent: str, path: str) -> bool:
        """Return whether this file lets the agent have the path."""
        if self.unparseable:
            return False
        group = self.group_for(agent)
        return True if group is None else group.allows(path)

    def crawl_delay_ms(self, agent: str) -> int | None:
        """Return the delay the file asks this agent to keep, if any."""
        group = self.group_for(agent)
        return None if group is None else group.crawl_delay_ms


ALLOW_EVERYTHING = Robots()
"""What a channel that returned four oh four for its robots file is taken to
have said. A missing file is a file that forbids nothing."""

ALLOW_NOTHING = Robots(unparseable=True)
"""What a channel that could not serve its robots file is taken to have said.
An error is not permission."""


def _match(pattern: str, path: str) -> bool:
    """Return whether a robots path pattern covers a path."""
    if pattern == "":
        return False
    anchored_end = pattern.endswith("$")
    body = pattern[:-1] if anchored_end else pattern
    parts = [re.escape(part) for part in body.split("*")]
    expression = ".*".join(parts)
    if anchored_end:
        expression += "$"
    return re.match(expression, path) is not None


def _delay_ms(value: str) -> int | None:
    try:
        seconds = float(value)
    except ValueError:
        return None
    if seconds < 0:
        return None
    return int(round(seconds * 1000))


def parse(text: str) -> Robots:
    """Read a robots file into groups, rules and sitemap lines."""
    if len(text.encode("utf-8", "replace")) > MAX_BYTES:
        return Robots(unparseable=True, source=text[:200])
    groups: list[Group] = []
    sitemaps: list[str] = []
    agents: list[str] = []
    rules: list[Rule] = []
    delay: int | None = None
    starting_group = False

    def flush() -> None:
        nonlocal agents, rules, delay
        if agents:
            groups.append(Group(tuple(agents), tuple(rules), delay))
        agents = []
        rules = []
        delay = None

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        name, _, value = line.partition(":")
        field_name = name.strip().lower()
        value = value.strip()
        if field_name == "user-agent":
            if not starting_group:
                flush()
                starting_group = True
            agents.append(value.lower())
            continue
        starting_group = False
        if field_name == "disallow":
            if value:
                rules.append(Rule(False, value))
        elif field_name == "allow":
            if value:
                rules.append(Rule(True, value))
        elif field_name == "crawl-delay":
            delay = _delay_ms(value)
        elif field_name == "sitemap":
            sitemaps.append(value)
    flush()
    return Robots(tuple(groups), tuple(sitemaps), False, text[:200])
