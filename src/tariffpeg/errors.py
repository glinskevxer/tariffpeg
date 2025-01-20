"""The error hierarchy every layer raises and the CLI turns into an exit code.

Nothing in this package raises a bare ``ValueError`` across a module boundary.
The unit has to be able to say why a harvest stopped without reading a stack
trace, so every refusal carries a stable ``code`` and the pieces of context the
operator needs to act on it.
"""

from __future__ import annotations


class TariffpegError(Exception):
    """Base class for every refusal this package raises on purpose.

    ``code`` is stable across releases. It appears in the CLI output and in the
    evidence ledger, so renaming one is a breaking change.
    """

    code = "error"

    def context(self) -> dict[str, str]:
        """Return the machine readable pieces of the failure.

        The default is empty. Subclasses that carry context override this so a
        caller can log the parts without parsing the message.
        """
        return {}


class NotFound(TariffpegError):
    """A record referenced by key is not in the store."""

    code = "not_found"

    def __init__(self, kind: str, ref: str) -> None:
        super().__init__(f"no {kind} with reference {ref!r}")
        self.kind = kind
        self.ref = ref

    def context(self) -> dict[str, str]:
        """Return the record kind and the reference that missed."""
        return {"kind": self.kind, "ref": self.ref}


class AlreadyExists(TariffpegError):
    """A record with this key is already in the store."""

    code = "already_exists"

    def __init__(self, kind: str, ref: str) -> None:
        super().__init__(f"{kind} {ref!r} is already registered")
        self.kind = kind
        self.ref = ref

    def context(self) -> dict[str, str]:
        """Return the record kind and the reference that collided."""
        return {"kind": self.kind, "ref": self.ref}


class Invalid(TariffpegError):
    """A value does not satisfy the rule stated for its field."""

    code = "invalid"

    def __init__(self, field: str, value: object, reason: str) -> None:
        super().__init__(f"{field} {value!r} is not accepted: {reason}")
        self.field = field
        self.value = value
        self.reason = reason

    def context(self) -> dict[str, str]:
        """Return the field, the rejected value and the stated reason."""
        return {"field": self.field, "value": repr(self.value), "reason": self.reason}


class Conflict(TariffpegError):
    """Two records disagree in a way the caller has to resolve."""

    code = "conflict"

    def __init__(self, subject: str, reason: str) -> None:
        super().__init__(f"{subject} cannot be applied: {reason}")
        self.subject = subject
        self.reason = reason

    def context(self) -> dict[str, str]:
        """Return the subject of the clash and why it cannot proceed."""
        return {"subject": self.subject, "reason": self.reason}
