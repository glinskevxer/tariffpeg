"""Filing a piece of paper is not doing the work."""

from __future__ import annotations

import datetime as dt

from tariffpeg.claims.rules import Persistence
from tariffpeg.model.period import StayMonth
from tariffpeg.model.remediation import Remediation
from tariffpeg.triage.remediation import (
    BEFORE_THE_WORK,
    apply,
    notices_by_claim,
)
from tests.triage.conftest import a_weighed


def notice(**over: object) -> Remediation:
    base: dict[str, object] = {
        "licence_serial": 4021,
        "claim_key": "lift",
        "reference": "RN-2026-0118",
        "filed_on": dt.date(2026, 3, 4),
        "effective_from": StayMonth(2026, 1),
        "accepted": True,
    }
    base.update(over)
    return Remediation(**base)  # type: ignore[arg-type]


def weighed_in(month: int, year: int = 2025, **over: object) -> object:
    item = a_weighed(**over)  # type: ignore[arg-type]
    from dataclasses import replace

    return replace(
        item,
        contradiction=replace(item.contradiction, stay=StayMonth(year, month)),
    )


def test_evidence_with_no_notice_is_left_alone() -> None:
    found = apply((a_weighed(),), {})
    assert found.weighed[0].weight == 5.0
    assert found.discounts == ()
    assert found.cleared == ()


def test_an_unaccepted_notice_discounts_nothing() -> None:
    found = apply((a_weighed(),), {"lift": notice(accepted=False)})
    assert found.weighed[0].weight == 5.0
    assert found.discounts == ()


def test_a_stay_before_the_work_is_cut_to_a_fraction() -> None:
    before = weighed_in(7, 2025)
    found = apply((before,), {"lift": notice()})  # type: ignore[arg-type]
    assert found.weighed[0].weight == 5.0 * BEFORE_THE_WORK[True]
    assert len(found.discounts) == 1
    assert found.discounts[0].reference == "RN-2026-0118"


def test_a_stay_after_the_work_counts_in_full() -> None:
    after = weighed_in(6, 2026)
    found = apply((after,), {"lift": notice()})  # type: ignore[arg-type]
    assert found.weighed[0].weight == 5.0
    assert found.discounts == ()


def test_a_stay_in_the_month_the_work_finished_counts_in_full() -> None:
    same = weighed_in(1, 2026)
    found = apply((same,), {"lift": notice()})  # type: ignore[arg-type]
    assert found.weighed[0].weight == 5.0


def test_a_transient_report_from_before_the_work_keeps_almost_nothing() -> None:
    before = weighed_in(7, 2025, persistence=Persistence.TRANSIENT)
    found = apply((before,), {"lift": notice()})  # type: ignore[arg-type]
    assert found.weighed[0].weight == 5.0 * BEFORE_THE_WORK[False]
    assert BEFORE_THE_WORK[False] < BEFORE_THE_WORK[True]


def test_a_particular_where_every_voice_predates_the_work_is_cleared() -> None:
    before = (weighed_in(7, 2025), weighed_in(8, 2025, review_key="seaboard:2"))
    found = apply(before, {"lift": notice()})  # type: ignore[arg-type]
    assert found.is_cleared("lift")
    assert found.cleared == ("lift",)


def test_a_particular_with_one_voice_after_the_work_is_not_cleared() -> None:
    mixed = (weighed_in(7, 2025), weighed_in(6, 2026, review_key="seaboard:2"))
    found = apply(mixed, {"lift": notice()})  # type: ignore[arg-type]
    assert not found.is_cleared("lift")


def test_a_cleared_particular_keeps_its_evidence_in_the_file() -> None:
    before = (weighed_in(7, 2025),)
    found = apply(before, {"lift": notice()})  # type: ignore[arg-type]
    assert len(found.for_claim("lift")) == 1
    assert found.for_claim("lift")[0].weight > 0


def test_a_notice_only_touches_its_own_particular() -> None:
    items = (a_weighed(claim_key="lift"), a_weighed(claim_key="breakfast_included"))
    found = apply(items, {"lift": notice()})
    assert found.for_claim("breakfast_included")[0].weight == 5.0
    assert found.cleared == ("lift",)


def test_the_discount_line_names_both_weights_and_the_notice() -> None:
    before = weighed_in(7, 2025)
    found = apply((before,), {"lift": notice()})  # type: ignore[arg-type]
    line = found.discounts[0].line()
    assert "cut from 5.00 to 1.00" in line
    assert "RN-2026-0118" in line


def test_the_notice_that_reaches_furthest_forward_is_the_one_that_is_used() -> None:
    early = notice(reference="RN-A", effective_from=StayMonth(2026, 1))
    late = notice(reference="RN-B", effective_from=StayMonth(2026, 3))
    picked = notices_by_claim([early, late])
    assert picked["lift"].reference == "RN-B"
    assert notices_by_claim([late, early])["lift"].reference == "RN-B"


def test_an_unaccepted_notice_never_becomes_the_one_that_is_used() -> None:
    assert notices_by_claim([notice(accepted=False)]) == {}


def test_notices_for_different_particulars_are_kept_apart() -> None:
    picked = notices_by_claim([notice(), notice(claim_key="breakfast_included", reference="RN-C")])
    assert sorted(picked) == ["breakfast_included", "lift"]


def test_applying_nothing_gives_nothing() -> None:
    found = apply((), {"lift": notice()})
    assert found.weighed == ()
    assert found.cleared == ()


def test_the_applied_evidence_and_its_discounts_are_the_shapes_they_say() -> None:
    from tariffpeg.triage.remediation import Applied, Discount

    found = apply((weighed_in(7, 2025),), {"lift": notice()})  # type: ignore[arg-type]
    assert isinstance(found, Applied)
    assert all(isinstance(item, Discount) for item in found.discounts)
