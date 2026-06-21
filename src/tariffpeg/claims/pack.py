"""The published rule pack.

Every rule here was written against real review text and every one of them has
a case in the suite that shows what it catches and a case that shows what it
leaves alone. Adding a rule without both is how a pack starts finding
contradictions that are not there.

The pack has a version because a case file cites it. An inspection that went out
on the strength of pack four has to be answerable in terms of pack four even
after pack five is published.
"""

from __future__ import annotations

from tariffpeg.claims.rules import ClaimRule, Persistence, Polarity, RulePack
from tariffpeg.errors import NotFound

METRES_A_MINUTE_WALKING = 80
"""What the unit converts a walk in minutes to. Guests write about minutes and
the licence is written in metres, so somewhere a number has to be picked. This
one is in the licensing guidance."""

METRES_A_MILE = 1609
"""Guests who write in miles are rounding to the half mile at best, so a rule
that reads one carries less weight than the same distance written in metres."""

STRUCTURAL = Persistence.STRUCTURAL
TRANSIENT = Persistence.TRANSIENT

PACK_ONE_RULES = (
    ClaimRule(
        "lift-absent",
        "lift",
        "(there is no|there was no|they have no|no) ... (lift|elevator)",
        Polarity.DENIES,
        STRUCTURAL,
        5,
        note="the guest says the premises has none at all",
    ),
    ClaimRule(
        "lift-out-of-order",
        "lift",
        "(lift|elevator) ... (out of order|not working|broken|out of service)",
        Polarity.DENIES,
        TRANSIENT,
        2,
        note="the lift exists and was not working during the stay",
    ),
    ClaimRule(
        "lift-used",
        "lift",
        "(took the lift|used the lift|lift to our floor|lift up to)",
        Polarity.AFFIRMS,
        STRUCTURAL,
        3,
    ),
    ClaimRule(
        "stairs-only",
        "lift",
        "(stairs only|only stairs|all the stairs|four flights|three flights)",
        Polarity.DENIES,
        STRUCTURAL,
        3,
    ),
    ClaimRule(
        "entrance-has-steps",
        "step_free_entrance",
        "(steps|step|stairs) ... (to get in|at the entrance|to the front door|up to the door)",
        Polarity.DENIES,
        STRUCTURAL,
        4,
    ),
    ClaimRule(
        "entrance-step-free",
        "step_free_entrance",
        "(no steps|level access|step free|ramp) ... (entrance|door|in)",
        Polarity.AFFIRMS,
        STRUCTURAL,
        3,
    ),
    ClaimRule(
        "bathroom-shared",
        "en_suite_all",
        "(shared|communal) ... (bathroom|shower|toilet)",
        Polarity.DENIES,
        STRUCTURAL,
        5,
    ),
    ClaimRule(
        "bathroom-shared-after",
        "en_suite_all",
        "(bathroom|shower|toilet) ... (was shared|is shared|shared with|shared between)",
        Polarity.DENIES,
        STRUCTURAL,
        5,
        note="the same finding with the words the other way round",
    ),
    ClaimRule(
        "bathroom-down-the-hall",
        "en_suite_all",
        "(bathroom|toilet|shower) ... (down the hall|along the corridor|on the landing)",
        Polarity.DENIES,
        STRUCTURAL,
        4,
    ),
    ClaimRule(
        "bathroom-en-suite",
        "en_suite_all",
        "(our own|private|en suite) ... (bathroom|shower)",
        Polarity.AFFIRMS,
        STRUCTURAL,
        2,
    ),
    ClaimRule(
        "breakfast-charged",
        "breakfast_included",
        "breakfast ... (was extra|cost extra|charged|not included|an extra)",
        Polarity.DENIES,
        STRUCTURAL,
        4,
    ),
    ClaimRule(
        "breakfast-not-served",
        "breakfast_included",
        "(no breakfast|breakfast was not served|nothing for breakfast)",
        Polarity.DENIES,
        TRANSIENT,
        2,
    ),
    ClaimRule(
        "breakfast-included",
        "breakfast_included",
        "breakfast ... (was included|included in the rate|came with the room)",
        Polarity.AFFIRMS,
        STRUCTURAL,
        3,
    ),
    ClaimRule(
        "parking-absent",
        "parking_on_site",
        "(no parking|nowhere to park|no car park)",
        Polarity.DENIES,
        STRUCTURAL,
        4,
    ),
    ClaimRule(
        "parking-off-site",
        "parking_on_site",
        "(park|parking) ... (in the street|on the road|down the road|in the village)",
        Polarity.DENIES,
        STRUCTURAL,
        3,
    ),
    ClaimRule(
        "parking-on-site",
        "parking_on_site",
        "(parked outside|car park|parking space)",
        Polarity.AFFIRMS,
        STRUCTURAL,
        2,
    ),
    ClaimRule(
        "wifi-patchy",
        "wifi_all_rooms",
        "(wifi|wi fi|internet) ... (only in the|not in the room|did not reach|no signal)",
        Polarity.DENIES,
        STRUCTURAL,
        3,
    ),
    ClaimRule(
        "wifi-down",
        "wifi_all_rooms",
        "(wifi|wi fi|internet) ... (was down|stopped working|kept dropping)",
        Polarity.DENIES,
        TRANSIENT,
        1,
    ),
    ClaimRule(
        "wifi-worked",
        "wifi_all_rooms",
        "(wifi|wi fi|internet) ... (was fine|worked well|in every room|throughout)",
        Polarity.AFFIRMS,
        STRUCTURAL,
        2,
    ),
    ClaimRule(
        "pets-refused",
        "pets_accepted",
        "(no dogs|dogs are not|would not take our dog|pets are not)",
        Polarity.DENIES,
        STRUCTURAL,
        4,
    ),
    ClaimRule(
        "pets-welcomed",
        "pets_accepted",
        "(brought our dog|dog was welcome|dog friendly)",
        Polarity.AFFIRMS,
        STRUCTURAL,
        3,
    ),
    ClaimRule(
        "late-arrival-refused",
        "late_arrival",
        "(nobody was there|no one was there|locked out|no answer) ... (when we arrived|at night)",
        Polarity.DENIES,
        TRANSIENT,
        3,
    ),
    ClaimRule(
        "late-arrival-staffed",
        "late_arrival",
        "(waited up for us|checked us in late|someone was there)",
        Polarity.AFFIRMS,
        STRUCTURAL,
        2,
    ),
    ClaimRule(
        "rooms-counted",
        "let_rooms",
        "(only|just) # (rooms|bedrooms)",
        Polarity.STATES,
        STRUCTURAL,
        2,
    ),
    ClaimRule(
        "rooms-in-the-house",
        "let_rooms",
        "# (rooms|bedrooms) (in the house|in total|altogether)",
        Polarity.STATES,
        STRUCTURAL,
        3,
    ),
    ClaimRule(
        "beds-counted",
        "bed_spaces",
        "(sleeps|beds for) #",
        Polarity.STATES,
        STRUCTURAL,
        2,
    ),
    ClaimRule(
        "parking-spaces-counted",
        "parking_spaces",
        "(only|just) # (spaces|parking spaces)",
        Polarity.STATES,
        STRUCTURAL,
        2,
    ),
    ClaimRule(
        "shore-metres",
        "shore_distance",
        "# (metres|meters|m) ... (beach|shore|sea|sand)",
        Polarity.STATES,
        STRUCTURAL,
        3,
    ),
    ClaimRule(
        "shore-minutes",
        "shore_distance",
        "# (minute|minutes|min) ... (beach|shore|sea|sand)",
        Polarity.STATES,
        STRUCTURAL,
        2,
        value_scale=METRES_A_MINUTE_WALKING,
    ),
    ClaimRule(
        "station-metres",
        "station_distance",
        "# (metres|meters|m) ... (station|platform)",
        Polarity.STATES,
        STRUCTURAL,
        3,
    ),
    ClaimRule(
        "station-minutes",
        "station_distance",
        "# (minute|minutes|min) ... (station|platform)",
        Polarity.STATES,
        STRUCTURAL,
        2,
        value_scale=METRES_A_MINUTE_WALKING,
    ),
    ClaimRule(
        "shore-metres-after",
        "shore_distance",
        "(beach|shore|sea|sand) ... # (metres|meters|m)",
        Polarity.STATES,
        STRUCTURAL,
        3,
        note="the same finding with the distance after the landmark",
    ),
    ClaimRule(
        "shore-minutes-after",
        "shore_distance",
        "(beach|shore|sea|sand) ... # (minute|minutes|min)",
        Polarity.STATES,
        STRUCTURAL,
        2,
        value_scale=METRES_A_MINUTE_WALKING,
    ),
    ClaimRule(
        "station-metres-after",
        "station_distance",
        "(station|platform) ... # (metres|meters|m)",
        Polarity.STATES,
        STRUCTURAL,
        3,
    ),
    ClaimRule(
        "station-minutes-after",
        "station_distance",
        "(station|platform) ... # (minute|minutes|min)",
        Polarity.STATES,
        STRUCTURAL,
        2,
        value_scale=METRES_A_MINUTE_WALKING,
    ),
)
"""The rules as pack one published them.

This tuple is frozen. A case file that cites pack one has to be answerable in
terms of pack one however many packs have been published since, and the only
way to promise that is to leave the list alone and add to a new one.
"""

ADDED_IN_TWO = (
    ClaimRule(
        "entrance-down-to-the-door",
        "step_free_entrance",
        "(down some steps|steps down|down a flight) ... (to the door|to reception|to the entrance)",
        Polarity.DENIES,
        STRUCTURAL,
        4,
        note="a basement entrance is as much of a barrier as one up a step",
    ),
    ClaimRule(
        "lift-too-small",
        "lift",
        "(lift|elevator) ... (was tiny|too small|only fits|barely fits)",
        Polarity.AFFIRMS,
        STRUCTURAL,
        2,
        note="a complaint about the lift is still evidence that there is one",
    ),
    ClaimRule(
        "bathroom-one-between",
        "en_suite_all",
        "(one bathroom|a single bathroom|one shower) ... (between|for all|for everyone)",
        Polarity.DENIES,
        STRUCTURAL,
        4,
    ),
    ClaimRule(
        "breakfast-paid-for",
        "breakfast_included",
        "(paid|charged|we were charged) ... (for breakfast|for the breakfast)",
        Polarity.DENIES,
        STRUCTURAL,
        3,
    ),
    ClaimRule(
        "parking-full",
        "parking_on_site",
        "(car park|the parking) ... (was full|never a space|always full)",
        Polarity.AFFIRMS,
        TRANSIENT,
        1,
        note="a full car park is a car park",
    ),
    ClaimRule(
        "pets-charged-for",
        "pets_accepted",
        "(charged|a charge|extra) ... (for the dog|for our dog|per dog)",
        Polarity.AFFIRMS,
        STRUCTURAL,
        2,
        note="a charge for the dog means the dog was taken",
    ),
    ClaimRule(
        "late-arrival-key-box",
        "late_arrival",
        "(key box|key safe|lock box|code for the box)",
        Polarity.DENIES,
        STRUCTURAL,
        3,
        note="a key safe is what a premises uses instead of staffing the door",
    ),
    ClaimRule(
        "shore-miles",
        "shore_distance",
        "# (mile|miles) ... (beach|shore|sea|sand)",
        Polarity.STATES,
        STRUCTURAL,
        1,
        value_scale=METRES_A_MILE,
    ),
    ClaimRule(
        "station-miles",
        "station_distance",
        "# (mile|miles) ... (station|platform)",
        Polarity.STATES,
        STRUCTURAL,
        1,
        value_scale=METRES_A_MILE,
    ),
    ClaimRule(
        "rooms-in-the-name",
        "let_rooms",
        "# (bedroom|bedroomed) (guest house|guesthouse|b and b|hotel)",
        Polarity.STATES,
        STRUCTURAL,
        3,
    ),
    ClaimRule(
        "beds-sleeps-up-to",
        "bed_spaces",
        "(sleeps up to|accommodates|room for) #",
        Polarity.STATES,
        STRUCTURAL,
        2,
    ),
    ClaimRule(
        "parking-spaces-there-are",
        "parking_spaces",
        "(there are|there were|they have) # (spaces|parking spaces)",
        Polarity.STATES,
        STRUCTURAL,
        3,
    ),
)
"""What pack two added on top of pack one."""

PACK_ONE = RulePack(1, PACK_ONE_RULES)
"""The first published pack, kept so an old case file can still be read."""

PACK_TWO = RulePack(2, (*PACK_ONE_RULES, *ADDED_IN_TWO))
"""The pack in force."""

PACKS = (PACK_ONE, PACK_TWO)
"""Every published pack, oldest first."""

PACK = PACK_TWO
"""The pack a case file cites unless it says otherwise."""


def pack_numbered(version: int) -> RulePack:
    """Return a published pack by its version, or refuse.

    Refusing beats falling back to the pack in force. A case file that names a
    version this build does not carry has to stop, because reading it against a
    later pack quietly changes what the operator was told.
    """
    for pack in PACKS:
        if pack.version == version:
            return pack
    raise NotFound("rule pack", str(version))


def published_versions() -> tuple[int, ...]:
    """Return the pack versions this build can read a case file against."""
    return tuple(pack.version for pack in PACKS)
