# Commands

<!-- Written by build_commands. Do not edit it here. -->

## `tariffpeg case`

Build the file an inspector is handed.

### `tariffpeg case bundle`

Write the pages behind a licence out as a bundle the fetcher can replay.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |
| `--to` | required | The directory to write the bundle into. |

### `tariffpeg case export`

Write the case file and its quotations out as files.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |
| `--to` | required | The directory to write the file and its quotations into. |
| `--at` |  | The month to decide at. |

### `tariffpeg case quotations`

List the quotations behind a case, with the captures they came from.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |
| `--at` |  | The month to decide at. |

### `tariffpeg case show`

Print the whole case file.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |
| `--at` |  | The month to decide at. |

## `tariffpeg channel`

Look after the channels the unit reads.

### `tariffpeg channel add`

Register a channel and the terms agreed with it.

| what | and | why |
| --- | --- | --- |
| `slug` | argument |  |
| `--name` | required | What the channel calls itself. |
| `--url` | required | The https base with no trailing slash. |
| `--syndication` |  | Whether the channel collects its own reviews or reproduces them. |
| `--scale` |  | The published dial this channel scores on. |
| `--delay` |  | The agreed crawl delay. |
| `--ceiling` |  | Requests a day this channel agreed to. |
| `--window` |  | The courtesy window, as 22-6. |
| `--pages` |  | Pages per property in one run. |
| `--locale` |  | The language the channel serves. |

### `tariffpeg channel list`

List the registered channels.

| what | and | why |
| --- | --- | --- |
| `--syndication` |  | Only channels of this kind. |

### `tariffpeg channel probe`

Read a channel robots file and set it against the terms agreed with us.

| what | and | why |
| --- | --- | --- |
| `slug` | argument |  |
| `--bundle` |  | Read from a recorded bundle instead of the network. |
| `--live` |  | Actually reach the channel. |

### `tariffpeg channel remove`

Take a channel off the register.

| what | and | why |
| --- | --- | --- |
| `slug` | argument |  |
| `--yes` |  | Confirm the action without prompting. |

### `tariffpeg channel show`

Print one channel and the terms agreed with it.

| what | and | why |
| --- | --- | --- |
| `slug` | argument |  |

## `tariffpeg config`

Look at the settings this run is using.

### `tariffpeg config check`

Read a settings file and say whether it is usable.

| what | and | why |
| --- | --- | --- |
| `path` | argument |  |

### `tariffpeg config defaults`

Print what the package ships with.

### `tariffpeg config show`

Print the settings in force.

| what | and | why |
| --- | --- | --- |
| `--changed-only` |  | Leave out anything still at its default. |

## `tariffpeg db`

Look after the evidence store.

### `tariffpeg db migrate`

Bring the store up to the schema this version expects.

### `tariffpeg db migrations`

List the migrations and whether they have run.

### `tariffpeg db status`

Say what the store holds.

### `tariffpeg db verify`

Check the store against itself and against this version.

## `tariffpeg harvest`

Plan and run the reading of the channels.

### `tariffpeg harvest plan`

Say where the next harvest would go.

| what | and | why |
| --- | --- | --- |
| `--at` |  | The month to measure the sample at. |
| `--on` |  | The day the harvest is being run on. |
| `--skipped` |  | Also say what was left out and why. |

### `tariffpeg harvest run`

Read the channels and put what comes back into the store.

| what | and | why |
| --- | --- | --- |
| `--profiles` | required | The file saying how each channel is read. |
| `--bundle` |  | Read from a recorded bundle instead of the network. |
| `--live` |  | Actually reach the channels. |
| `--at` |  | The month to measure the sample at. |
| `--on` |  | The day the harvest is being run on. |
| `--problems` |  | Also print what each page could not read. |

## `tariffpeg letter`

Look after what the unit sent and what came back.

### `tariffpeg letter list`

List what has gone out.

| what | and | why |
| --- | --- | --- |
| `--licence` |  | Only letters about this licence. |
| `--operator` |  | Only letters to this operator. |
| `--unanswered` |  | Only the ones nobody has answered. |

### `tariffpeg letter overdue`

List the letters nobody has answered in time.

| what | and | why |
| --- | --- | --- |
| `--on` |  | The day to reckon from, today if left out. |

### `tariffpeg letter reply`

Record that the operator answered.

| what | and | why |
| --- | --- | --- |
| `reference` | argument |  |
| `--on` |  | The day the reply came, today if left out. |

### `tariffpeg letter send`

Record that a letter went out to the operator of a licence.

| what | and | why |
| --- | --- | --- |
| `reference` | argument |  |
| `licence_ref` | argument |  |
| `--kind` | required | What kind of letter it is. |
| `--subject` | required | What the letter is about. |
| `--body` | required | The text that went out, so it can be digested. |
| `--on` |  | The day it went, today if left out. |

## `tariffpeg licence`

Look after the register of licensed premises.

### `tariffpeg licence add`

Put a licence on the register.

| what | and | why |
| --- | --- | --- |
| `serial` | argument |  |
| `--name` | required | The trading name on the plaque. |
| `--operator` | required | Who holds the licence. |
| `--locality` | required | Which village or town it is in. |
| `--from` | required | The day the licence period starts. |
| `--to` | required | The day the licence period ends. |
| `--closed` |  | Months the premises shuts, as 1,2,3. |
| `--particular` |  | A particular, as key=value. |

### `tariffpeg licence list`

List what is on the register.

| what | and | why |
| --- | --- | --- |
| `--locality` |  | Only this locality. |
| `--status` |  | Only licences in this status. |

### `tariffpeg licence particulars`

List the particulars the licensing order recognises.

### `tariffpeg licence remove`

Take a licence off the register, reviews and all.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |
| `--yes` |  | Confirm the action without prompting. |

### `tariffpeg licence show`

Print one licence and everything it declares.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |

### `tariffpeg licence status`

Move a licence into another status.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |
| `status` | argument |  |

### `tariffpeg licence vary`

Change what a licence declares.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |
| `--particular` | required | A particular to change, as key=value. |

## `tariffpeg listing`

Look after which page is which premises.

### `tariffpeg listing add`

Record which page on a channel is a licensed premises.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |
| `channel` | argument |  |
| `--path` | required | The path on the channel, starting at the root. |
| `--property-ref` | required | How the channel numbers this property. |
| `--confirmed` |  | The day somebody looked at the page, today if left out. |
| `--note` |  | How the listing was confirmed. |

### `tariffpeg listing confirm`

Say that somebody has looked at the page and it is still the right one.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |
| `channel` | argument |  |
| `--on` |  | The day to reckon from, today if left out. |

### `tariffpeg listing list`

List what has been recorded.

| what | and | why |
| --- | --- | --- |
| `--licence` |  | Only this licence. |
| `--channel` |  | Only this channel. |
| `--all` |  | Include retired listings. |

### `tariffpeg listing retire`

Stop fetching a listing, and say why.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |
| `channel` | argument |  |
| `--why` | required | Why the listing is no longer worth fetching. |

### `tariffpeg listing stale`

List the listings nobody has looked at lately.

| what | and | why |
| --- | --- | --- |
| `--on` |  | The day to reckon from, today if left out. |

## `tariffpeg operator`

Look after the register of who holds the licences.

### `tariffpeg operator add`

Put an operator on the register.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |
| `--name` | required | The name on the licence. |
| `--contact` | required | The person a letter is addressed to. |
| `--email` | required | Where a letter goes. |
| `--address` | required | The address on the register. |
| `--registered` |  | The day they joined the register, today if left out. |
| `--note` |  | Anything the unit wants on the file. |

### `tariffpeg operator contact`

Change who a letter to this operator is addressed to.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |
| `--contact` | required | The person a letter is addressed to. |
| `--email` | required | Where a letter goes. |

### `tariffpeg operator hold`

Tie a licence to an operator on the register.

| what | and | why |
| --- | --- | --- |
| `licence_ref` | argument |  |
| `operator_ref` | argument |  |

### `tariffpeg operator list`

List the operators on the register.

| what | and | why |
| --- | --- | --- |
| `--holding` |  | Only those holding more than this many. |

### `tariffpeg operator remove`

Take an operator off the register, if they hold nothing.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |
| `--yes` |  | Confirm the action without prompting. |

### `tariffpeg operator show`

Print one operator and the licences they hold.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |

## `tariffpeg remediation`

Look after the notices operators file.

### `tariffpeg remediation accept`

Accept a notice, which discounts the evidence from before the work.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |
| `claim` | argument |  |
| `reference` | argument |  |
| `--note` |  | What was produced in support. |

### `tariffpeg remediation file`

Take a notice on file. It is not accepted until somebody accepts it.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |
| `claim` | argument |  |
| `--reference` | required | The number the notice was filed under. |
| `--filed` | required | The day the operator filed the notice. |
| `--effective` | required | The month the work finished, as 2026-01. |
| `--note` |  | What the operator sent with it. |

### `tariffpeg remediation list`

List the notices on file for a licence.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |
| `--accepted-only` |  | Leave out anything not accepted. |

### `tariffpeg remediation refuse`

Refuse a notice, and record why.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |
| `claim` | argument |  |
| `reference` | argument |  |
| `--why` | required | Why the notice was not accepted. |

## `tariffpeg review`

Look at the reviews the unit is holding.

### `tariffpeg review list`

List the reviews held.

| what | and | why |
| --- | --- | --- |
| `--licence` |  | Only this licence. |
| `--channel` |  | Only this channel. |
| `--season` |  | Only stays in this season. |

### `tariffpeg review show`

Print one review and the capture behind it.

| what | and | why |
| --- | --- | --- |
| `key` | argument |  |

## `tariffpeg sample`

Look at how far the statutory sample has got.

### `tariffpeg sample coverage`

Print the coverage for one licence.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |
| `--at` |  | The month to measure at. |

### `tariffpeg sample regime`

Print what the regime asks of one licence and why.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |

### `tariffpeg sample shortfall`

List the licences that are short, worst first.

| what | and | why |
| --- | --- | --- |
| `--at` |  | The month to measure at. |

## `tariffpeg triage`

Decide what happens to the licences.

### `tariffpeg triage list`

List what the unit would do about every active licence.

| what | and | why |
| --- | --- | --- |
| `--at` |  | The month to decide at. |
| `--needing-a-visit` |  | Only the ones that send somebody out. |

### `tariffpeg triage schedule`

Book a visit for everything that needs one.

| what | and | why |
| --- | --- | --- |
| `--at` |  | The month to decide at. |
| `--on` |  | The day the decision is being made on. |

### `tariffpeg triage show`

Print the findings behind one decision.

| what | and | why |
| --- | --- | --- |
| `ref` | argument |  |
| `--at` |  | The month to decide at. |
