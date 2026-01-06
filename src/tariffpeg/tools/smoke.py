"""One run of the whole thing, end to end, against pages written here.

This is the test that would have caught every release problem this package has
had, because every one of them was a seam between two layers that each had their
own tests. It builds a store, registers a channel and a licence, replays two
pages of reviews, and reads the case file that comes out the other end.

Nothing here touches the network and nothing is left behind.
"""

from __future__ import annotations

import datetime as dt
import sys
import tempfile
from pathlib import Path

from tariffpeg import service
from tariffpeg.claims.pack import PACK
from tariffpeg.clock import FixedClock
from tariffpeg.fetch.replay import ReplayTransport
from tariffpeg.harvest.runner import Runner
from tariffpeg.harvest.session import Session
from tariffpeg.model.channel import Channel, FetchPolicy, SyndicationClass
from tariffpeg.model.licence import Licence
from tariffpeg.model.listing import Listing
from tariffpeg.model.period import StayMonth
from tariffpeg.model.remediation import Remediation
from tariffpeg.parse.profile import FieldRule, Profile
from tariffpeg.settings import DEFAULTS
from tariffpeg.store.channels import ChannelStore
from tariffpeg.store.db import Database
from tariffpeg.store.licences import LicenceStore
from tariffpeg.store.listings import ListingStore
from tariffpeg.store.migrations import migrate
from tariffpeg.store.remediations import RemediationStore
from tariffpeg.triage.disposition import Disposition

NAME = "smoke"

STARTED = dt.datetime(2026, 6, 1, 22, 30, tzinfo=dt.UTC)
AT = StayMonth(2026, 6)
BASE = "https://seaboard.example"
LISTING_PATH = "/property/4021/reviews"

REVIEWS = (
    (
        "91188",
        "There is no lift at all and we carried the cases up three flights.",
        "8.4",
        "July 2025",
    ),
    (
        "91190",
        "They have no lift, which the listing never mentioned anywhere.",
        "7.0",
        "August 2025",
    ),
    ("91191", "Breakfast was charged at twelve pounds a head on every morning.", "6.0", "May 2025"),
    (
        "91192",
        "The harbour walk starts outside and the bread at breakfast was good.",
        "9.0",
        "June 2025",
    ),
)


def _page(reviews: tuple[tuple[str, str, str, str], ...], following: str = "") -> str:
    blocks = "".join(
        f'<article class="review" data-id="{number}">'
        f'<p class="body">{body}</p>'
        f'<span class="score" data-value="{score}">{score}</span>'
        f'<span class="stay">{stay}</span>'
        "</article>"
        for number, body, score, stay in reviews
    )
    link = f'<a class="next" href="{following}">next</a>' if following else ""
    return f'<html><body><div id="reviews">{blocks}</div>{link}</body></html>'


def profile() -> Profile:
    """Return the profile the smoke run reads with."""
    return Profile(
        channel="seaboard",
        version=1,
        container="article.review",
        fields=(
            FieldRule("channel_review_id", "attribute", "article.review", "data-id", required=True),
            FieldRule("body", "text", "p.body", required=True),
            FieldRule("score", "attribute", "span.score", "data-value", required=True),
            FieldRule("stay_month", "text", "span.stay"),
        ),
        next_page="a.next",
    )


def transport() -> ReplayTransport:
    """Return a recording of the two pages the smoke run reads."""
    replay = ReplayTransport()
    replay.add(f"{BASE}/robots.txt", "User-agent: *\nDisallow: /admin\n")
    replay.add(f"{BASE}{LISTING_PATH}", _page(REVIEWS[:2], f"{BASE}{LISTING_PATH}?page=2"))
    replay.add(f"{BASE}{LISTING_PATH}?page=2", _page(REVIEWS[2:]))
    return replay


def stock(db: Database) -> None:
    """Put a channel, a licence and a listing on the register."""
    ChannelStore(db).add(
        Channel(
            slug="seaboard",
            name="Seaboard Stays",
            base_url=BASE,
            syndication=SyndicationClass.PRIMARY,
            policy=FetchPolicy(DEFAULTS.user_agent, 250, 400),
        )
    )
    LicenceStore(db).add(
        Licence(
            serial=4021,
            trading_name="The Anchor Rooms",
            operator_name="Pellow and Daughter",
            locality="Porthgwarra",
            period_start=dt.date(2025, 1, 1),
            period_end=dt.date(2027, 12, 31),
            particulars={
                "grading_band": 3,
                "let_rooms": 9,
                "bed_spaces": 18,
                "lift": True,
                "breakfast_included": True,
            },
        )
    )
    ListingStore(db).add(Listing(4021, "seaboard", LISTING_PATH, "P-88213", dt.date(2026, 1, 5)))


class Ticking:
    """A clock that steps a second every time the run reads it."""

    def __init__(self, at: dt.datetime) -> None:
        self._at = at

    def now(self) -> dt.datetime:
        """Return the next second."""
        self._at = self._at + dt.timedelta(seconds=1)
        return self._at


def run_once(db: Database) -> list[str]:
    """Run the whole pipeline against the recording and return what it said."""
    stock(db)
    plan = service.plan(db, AT, STARTED.date())
    if not plan.stops:
        raise AssertionError(f"the plan visited nothing: {plan.skipped}")
    runner = Runner(
        db,
        Session(transport()),
        service.channels(db),
        {"seaboard": profile()},
        Ticking(STARTED),
    )
    report = runner.run(plan)
    if report.reviews_new != len(REVIEWS):
        raise AssertionError(f"{report.reviews_new} reviews stored, wanted {len(REVIEWS)}")
    licence = LicenceStore(db).get(4021)
    case = service.case_for(db, licence, AT, PACK)
    claims = {finding.claim_key for finding in case.decision.findings}
    if "lift" not in claims:
        raise AssertionError(f"the lift was not found against the licence: {claims}")
    if case.decision.disposition is Disposition.NO_ACTION:
        raise AssertionError("two guests saying there is no lift produced no action")
    if not case.quotations:
        raise AssertionError("the case file quoted nothing")
    for quotation in case.quotations:
        if not quotation.capture_digest.startswith("sha256:") or quotation.fetched_at is None:
            raise AssertionError(f"{quotation.review_key} cannot be answered for")
    RemediationStore(db).add(
        Remediation(4021, "lift", "RN-1", dt.date(2026, 5, 4), StayMonth(2026, 1)).accept("seen")
    )
    cleared = service.case_for(db, licence, AT, PACK)
    if not cleared.applied.is_cleared("lift"):
        raise AssertionError("an accepted notice did not clear the evidence before it")
    if cleared.decision.score >= case.decision.score:
        raise AssertionError("an accepted notice did not reduce the score")
    return [
        f"{report.pages_read} pages read, {report.reviews_new} reviews held",
        f"coverage {case.coverage.opinions} opinions, {case.coverage.total_shortfall} short",
        f"disposition {case.decision.disposition} at {case.decision.score:.2f}",
        f"after the notice {cleared.decision.disposition} at {cleared.decision.score:.2f}",
    ]


def main() -> int:
    """Run the smoke run and return an exit code."""
    quiet = "--quiet" in sys.argv[1:]
    with (
        tempfile.TemporaryDirectory() as scratch,
        Database(Path(scratch) / "smoke.sqlite3") as db,
    ):
        migrate(db, FixedClock(STARTED))
        try:
            lines = run_once(db)
        except AssertionError as err:
            print(f"{NAME}: {err}")
            return 1
    if not quiet:
        for line in lines:
            print(f"{NAME}: {line}")
    print(f"{NAME}: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
