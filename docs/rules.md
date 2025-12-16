# Rule pack

<!-- Written by build_rules. Do not edit it here. -->

Pack version 1, 35 rules.

A structural rule describes a feature of the premises. A transient one describes something that was true for a stay. The two decay at different rates and the second needs company before it is worth a visit.

A walk in minutes is read as 80 metres a minute.

## bed_spaces

Bed spaces across all let rooms. Measured as a count.
Tolerance 2, either way.

| rule | pattern | says | kind | weight |
| --- | --- | --- | --- | --- |
| `beds-counted` | `(sleeps\|beds for) #` | states | structural | 2 |

## breakfast_included

Breakfast is in the room rate. Measured as a flag.

| rule | pattern | says | kind | weight |
| --- | --- | --- | --- | --- |
| `breakfast-charged` | `breakfast ... (was extra\|cost extra\|charged\|not included\|an extra)` | denies | structural | 4 |
| `breakfast-not-served` | `(no breakfast\|breakfast was not served\|nothing for breakfast)` | denies | transient | 2 |
| `breakfast-included` | `breakfast ... (was included\|included in the rate\|came with the room)` | affirms | structural | 3 |

## en_suite_all

Every let room is en suite. Measured as a flag.

| rule | pattern | says | kind | weight |
| --- | --- | --- | --- | --- |
| `bathroom-shared` | `(shared\|communal) ... (bathroom\|shower\|toilet)` | denies | structural | 5 |
| `bathroom-shared-after` | `(bathroom\|shower\|toilet) ... (was shared\|is shared\|shared with\|shared between)` | denies | structural | 5 |
| `bathroom-down-the-hall` | `(bathroom\|toilet\|shower) ... (down the hall\|along the corridor\|on the landing)` | denies | structural | 4 |
| `bathroom-en-suite` | `(our own\|private\|en suite) ... (bathroom\|shower)` | affirms | structural | 2 |

`bathroom-shared-after`: the same finding with the words the other way round.

## late_arrival

Arrival after ten at night is staffed. Measured as a flag.

| rule | pattern | says | kind | weight |
| --- | --- | --- | --- | --- |
| `late-arrival-refused` | `(nobody was there\|no one was there\|locked out\|no answer) ... (when we arrived\|at night)` | denies | transient | 3 |
| `late-arrival-staffed` | `(waited up for us\|checked us in late\|someone was there)` | affirms | structural | 2 |

## let_rooms

Rooms let to guests. Measured as a count.

| rule | pattern | says | kind | weight |
| --- | --- | --- | --- | --- |
| `rooms-counted` | `(only\|just) # (rooms\|bedrooms)` | states | structural | 2 |
| `rooms-in-the-house` | `# (rooms\|bedrooms) (in the house\|in total\|altogether)` | states | structural | 3 |

## lift

A passenger lift serves the guest floors. Measured as a flag.

| rule | pattern | says | kind | weight |
| --- | --- | --- | --- | --- |
| `lift-absent` | `(there is no\|there was no\|they have no\|no) ... (lift\|elevator)` | denies | structural | 5 |
| `lift-out-of-order` | `(lift\|elevator) ... (out of order\|not working\|broken\|out of service)` | denies | transient | 2 |
| `lift-used` | `(took the lift\|used the lift\|lift to our floor\|lift up to)` | affirms | structural | 3 |
| `stairs-only` | `(stairs only\|only stairs\|all the stairs\|four flights\|three flights)` | denies | structural | 3 |

`lift-absent`: the guest says the premises has none at all.
`lift-out-of-order`: the lift exists and was not working during the stay.

## parking_on_site

Parking is on the premises. Measured as a flag.

| rule | pattern | says | kind | weight |
| --- | --- | --- | --- | --- |
| `parking-absent` | `(no parking\|nowhere to park\|no car park)` | denies | structural | 4 |
| `parking-off-site` | `(park\|parking) ... (in the street\|on the road\|down the road\|in the village)` | denies | structural | 3 |
| `parking-on-site` | `(parked outside\|car park\|parking space)` | affirms | structural | 2 |

## parking_spaces

Marked parking spaces. Measured as a count.
Tolerance 1, either way.

| rule | pattern | says | kind | weight |
| --- | --- | --- | --- | --- |
| `parking-spaces-counted` | `(only\|just) # (spaces\|parking spaces)` | states | structural | 2 |

## pets_accepted

Dogs are accepted in let rooms. Measured as a flag.

| rule | pattern | says | kind | weight |
| --- | --- | --- | --- | --- |
| `pets-refused` | `(no dogs\|dogs are not\|would not take our dog\|pets are not)` | denies | structural | 4 |
| `pets-welcomed` | `(brought our dog\|dog was welcome\|dog friendly)` | affirms | structural | 3 |

## shore_distance

Walking metres to the shore. Measured as a distance_m.
Tolerance 150, over only.

| rule | pattern | says | kind | weight |
| --- | --- | --- | --- | --- |
| `shore-metres` | `# (metres\|meters\|m) ... (beach\|shore\|sea\|sand)` | states | structural | 3 |
| `shore-minutes` | `# (minute\|minutes\|min) ... (beach\|shore\|sea\|sand)` | states | structural | 2 |
| `shore-metres-after` | `(beach\|shore\|sea\|sand) ... # (metres\|meters\|m)` | states | structural | 3 |
| `shore-minutes-after` | `(beach\|shore\|sea\|sand) ... # (minute\|minutes\|min)` | states | structural | 2 |

`shore-metres-after`: the same finding with the distance after the landmark.

## station_distance

Walking metres to the station. Measured as a distance_m.
Tolerance 250, over only.

| rule | pattern | says | kind | weight |
| --- | --- | --- | --- | --- |
| `station-metres` | `# (metres\|meters\|m) ... (station\|platform)` | states | structural | 3 |
| `station-minutes` | `# (minute\|minutes\|min) ... (station\|platform)` | states | structural | 2 |
| `station-metres-after` | `(station\|platform) ... # (metres\|meters\|m)` | states | structural | 3 |
| `station-minutes-after` | `(station\|platform) ... # (minute\|minutes\|min)` | states | structural | 2 |

## step_free_entrance

The main entrance is step free. Measured as a flag.

| rule | pattern | says | kind | weight |
| --- | --- | --- | --- | --- |
| `entrance-has-steps` | `(steps\|step\|stairs) ... (to get in\|at the entrance\|to the front door\|up to the door)` | denies | structural | 4 |
| `entrance-step-free` | `(no steps\|level access\|step free\|ramp) ... (entrance\|door\|in)` | affirms | structural | 3 |

## wifi_all_rooms

Wireless internet reaches every room. Measured as a flag.

| rule | pattern | says | kind | weight |
| --- | --- | --- | --- | --- |
| `wifi-patchy` | `(wifi\|wi fi\|internet) ... (only in the\|not in the room\|did not reach\|no signal)` | denies | structural | 3 |
| `wifi-down` | `(wifi\|wi fi\|internet) ... (was down\|stopped working\|kept dropping)` | denies | transient | 1 |
| `wifi-worked` | `(wifi\|wi fi\|internet) ... (was fine\|worked well\|in every room\|throughout)` | affirms | structural | 2 |
