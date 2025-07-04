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

METRES_A_MINUTE_WALKING = 80
"""What the unit converts a walk in minutes to. Guests write about minutes and
the licence is written in metres, so somewhere a number has to be picked. This
one is in the licensing guidance."""

STRUCTURAL = Persistence.STRUCTURAL
TRANSIENT = Persistence.TRANSIENT

RULES = (
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
"""Every published rule, in the order the pack lists them."""

PACK = RulePack(1, RULES)
"""The pack a case file cites unless it says otherwise."""
