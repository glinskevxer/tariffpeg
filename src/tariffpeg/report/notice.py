"""The letter that goes to the operator, drafted from the file it is about.

The letter is drafted here rather than typed, because a letter typed from a case
file and a case file are two documents that drift apart. What goes in the post
has to say the same thing the file says, in the operator's terms rather than the
unit's, and it has to quote what was said about their premises.

A draft is not a sent letter. Nothing here writes to the register. The draft is
run off, read by whoever signs it, and only then does its digest go into the
correspondence register against a reference. That order is deliberate: a letter
recorded as sent before anybody read it is a letter the unit cannot answer for.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from tariffpeg.errors import Conflict
from tariffpeg.model.determination import Determination
from tariffpeg.model.letter import REPLY_DAYS, Letter, Sent
from tariffpeg.model.outcome import Disposition
from tariffpeg.report.casefile import CaseFile
from tariffpeg.workdays import add_working_days

MAX_REMINDERS = 2
"""How many times an operator is chased before the unit stops writing.

The third letter is not a letter. An operator who has ignored two of them is
answered by sending somebody to the premises, and the file says that is what
happened rather than showing a fourth reminder nobody read.
"""

KIND_FOR = {
    Disposition.DESK_ENQUIRY: Sent.DESK_ENQUIRY,
    Disposition.REINSPECTION: Sent.NOTICE_OF_INSPECTION,
    Disposition.URGENT: Sent.NOTICE_OF_INSPECTION,
}
"""Which kind of letter each disposition produces."""

QUOTES_PER_FINDING = 3
"""How many things guests said go in the letter for each particular.

All of them would be fairer and none of them would be readable. Three is what
the unit settled on, and the file behind the letter carries the rest."""


@dataclass(frozen=True, slots=True)
class Draft:
    """A letter, written but not sent."""

    licence_serial: int
    licence_ref: str
    operator_name: str
    kind: Sent
    subject: str
    paragraphs: tuple[str, ...]
    reply_by: dt.date

    def lines(self) -> tuple[str, ...]:
        """Return the letter as it would be printed."""
        out: list[str] = [
            f"Our reference: {self.licence_ref}",
            f"For the attention of {self.operator_name}",
            "",
            self.subject,
            "",
        ]
        for paragraph in self.paragraphs:
            out.append(paragraph)
            out.append("")
        out.append(f"Please reply by {self.reply_by}.")
        return tuple(out)

    def text(self) -> str:
        """Return the letter as one block, which is what gets a digest."""
        return "\n".join(self.lines()) + "\n"


def _finding_paragraph(claim_key: str, declared: str, quotes: tuple[str, ...]) -> str:
    said = "; ".join(f'"{quote}"' for quote in quotes[:QUOTES_PER_FINDING])
    return (
        f"Your licence records {claim_key} as {declared}. Guests staying with you"
        f" have written: {said}."
    )


def draft(case: CaseFile, minute: Determination | None, sent_on: dt.date) -> Draft:
    """Return the letter a case file produces, or refuse if it produces none.

    A file that came out at no action is not a letter. Writing to an operator to
    tell them nothing was found teaches them that a letter from this unit can be
    ignored, and the next one cannot afford that.
    """
    disposition = case.decision.disposition
    if disposition not in KIND_FOR:
        raise Conflict("letter", f"a {disposition} does not produce a letter")
    kind = KIND_FOR[disposition]
    paragraphs = [
        f"We have reviewed what guests have written about {case.licence.trading_name}"
        f" for stays up to {case.decided_at}."
    ]
    for finding in case.decision.findings:
        quotes = tuple(item.quote for item in case.quotations_for(finding.claim_key))
        if not quotes:
            continue
        paragraphs.append(_finding_paragraph(finding.claim_key, finding.declared, quotes))
    if kind is Sent.NOTICE_OF_INSPECTION:
        paragraphs.append(
            "An officer will visit the premises. You do not need to do anything"
            " before the visit beyond telling us if the dates below do not suit."
        )
    else:
        paragraphs.append(
            "Please tell us whether the particulars above are still correct, and"
            " if they are not, what you have changed and when."
        )
    if minute is not None:
        paragraphs.append(
            f"This letter follows the determination minuted on {minute.decided_at}"
            f" under rule pack {minute.pack_version}."
        )
    if case.decision.capped:
        paragraphs.append(
            "We have not yet read every channel your premises is listed on, so"
            " this letter asks a question rather than reaching a conclusion."
        )
    return Draft(
        licence_serial=case.licence.serial,
        licence_ref=case.licence.ref,
        operator_name=case.licence.operator_name,
        kind=kind,
        subject=f"Accommodation standards: {case.licence.trading_name}",
        paragraphs=tuple(paragraphs),
        reply_by=add_working_days(sent_on, REPLY_DAYS[kind]),
    )


def reminder(original: Letter, chased_before: int, sent_on: dt.date) -> Draft:
    """Return the reminder that follows an unanswered letter, or refuse.

    The reminder repeats what was asked rather than restating the evidence. An
    operator who did not answer the first letter is not helped by a longer one,
    and the evidence has not changed since it went.
    """
    if original.answered:
        raise Conflict("reminder", f"{original.reference} was answered on {original.replied_on}")
    if original.kind is Sent.REMINDER:
        raise Conflict("reminder", "a reminder is chased by a visit, not by another reminder")
    if chased_before >= MAX_REMINDERS:
        raise Conflict(
            "reminder",
            f"this licence has had {chased_before} reminders, which is where writing stops",
        )
    ordinal = "second" if chased_before else "first"
    return Draft(
        licence_serial=original.licence_serial,
        licence_ref=original.reference,
        operator_name=original.operator_ref,
        kind=Sent.REMINDER,
        subject=f"Reminder: {original.subject}",
        paragraphs=(
            f"We wrote to you on {original.sent_on} about {original.subject.lower()}"
            f" and asked for a reply by {original.due_on()}. We have not had one.",
            f"This is the {ordinal} reminder. If we do not hear from you an officer"
            " will visit the premises without a further letter.",
        ),
        reply_by=add_working_days(sent_on, REPLY_DAYS[Sent.REMINDER]),
    )
