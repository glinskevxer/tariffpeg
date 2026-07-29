# Architecture

<!-- Written by build_architecture. Do not edit it here. -->

A layer may import the layers listed against it and nothing else. The check that enforces this is `check_layers`.

| layer | what it is for | may import |
| --- | --- | --- |
| (base) | The errors, the identifiers, the clock and the settings. | (base) |
| model | The records the store holds and the rules about what they may contain. | (base), model |
| fetch | Talking to a channel, or replaying what a channel said. | (base), model, fetch |
| parse | Turning a served page into the reviews on it. | (base), model, parse |
| normalise | Turning what came off a page into something the store will accept. | (base), model, parse, normalise |
| dedupe | Working out when two reviews are the same review. | (base), model, dedupe |
| claims | Setting what a guest said against what the operator signed for. | (base), model, claims |
| sample | How many reviews a licence has to be sampled with. | (base), model, dedupe, sample |
| store | The one SQLite file, and everything that reads or writes it. | (base), model, store |
| harvest | Planning a run and walking it. | (base), model, fetch, parse, normalise, sample, store, harvest |
| triage | Weighing the evidence and deciding what happens. | (base), model, claims, dedupe, sample, triage |
| report | The case file an inspector is handed. | (base), model, claims, dedupe, sample, triage, report |
| cli | The commands the unit types. | anything |
| tools | The checks and the generated documents. Nothing imports these. | anything |

These modules join the layers up and may import anything: `tariffpeg.service`.

## What is in each layer

### (base)

- `tariffpeg.clock`
- `tariffpeg.errors`
- `tariffpeg.ids`
- `tariffpeg.service`
- `tariffpeg.settings`
- `tariffpeg.workdays`

### model

- `tariffpeg.model.capture`
- `tariffpeg.model.channel`
- `tariffpeg.model.letter`
- `tariffpeg.model.licence`
- `tariffpeg.model.listing`
- `tariffpeg.model.operator`
- `tariffpeg.model.outcome`
- `tariffpeg.model.particulars`
- `tariffpeg.model.period`
- `tariffpeg.model.profile`
- `tariffpeg.model.redaction`
- `tariffpeg.model.remediation`
- `tariffpeg.model.review`
- `tariffpeg.model.scale`

### fetch

- `tariffpeg.fetch.backoff`
- `tariffpeg.fetch.bundle`
- `tariffpeg.fetch.live`
- `tariffpeg.fetch.pacer`
- `tariffpeg.fetch.replay`
- `tariffpeg.fetch.robots`
- `tariffpeg.fetch.transport`

### parse

- `tariffpeg.parse.dom`
- `tariffpeg.parse.drift`
- `tariffpeg.parse.extract`
- `tariffpeg.parse.jsonld`
- `tariffpeg.parse.loader`
- `tariffpeg.parse.profile`
- `tariffpeg.parse.select`
- `tariffpeg.parse.tokens`

### normalise

- `tariffpeg.normalise.register`
- `tariffpeg.normalise.review`

### dedupe

- `tariffpeg.dedupe.shingle`
- `tariffpeg.dedupe.syndication`

### claims

- `tariffpeg.claims.contradiction`
- `tariffpeg.claims.grammar`
- `tariffpeg.claims.pack`
- `tariffpeg.claims.rules`

### sample

- `tariffpeg.sample.calibration`
- `tariffpeg.sample.coverage`
- `tariffpeg.sample.regime`

### store

- `tariffpeg.store.captures`
- `tariffpeg.store.channels`
- `tariffpeg.store.db`
- `tariffpeg.store.letters`
- `tariffpeg.store.licences`
- `tariffpeg.store.listings`
- `tariffpeg.store.migrations`
- `tariffpeg.store.operators`
- `tariffpeg.store.profiles`
- `tariffpeg.store.remediations`
- `tariffpeg.store.retention`
- `tariffpeg.store.reviews`

### harvest

- `tariffpeg.harvest.budget`
- `tariffpeg.harvest.plan`
- `tariffpeg.harvest.runner`
- `tariffpeg.harvest.session`

### triage

- `tariffpeg.triage.corroborate`
- `tariffpeg.triage.disposition`
- `tariffpeg.triage.remediation`
- `tariffpeg.triage.rooms`
- `tariffpeg.triage.schedule`
- `tariffpeg.triage.weight`

### report

- `tariffpeg.report.casefile`
- `tariffpeg.report.explanation`
- `tariffpeg.report.locality`
- `tariffpeg.report.rows`
- `tariffpeg.report.summary`
- `tariffpeg.report.workload`

### cli

- `tariffpeg.cli.case`
- `tariffpeg.cli.channel`
- `tariffpeg.cli.config`
- `tariffpeg.cli.context`
- `tariffpeg.cli.db`
- `tariffpeg.cli.harvest`
- `tariffpeg.cli.letter`
- `tariffpeg.cli.licence`
- `tariffpeg.cli.listing`
- `tariffpeg.cli.main`
- `tariffpeg.cli.operator`
- `tariffpeg.cli.profile`
- `tariffpeg.cli.remediation`
- `tariffpeg.cli.review`
- `tariffpeg.cli.sample`
- `tariffpeg.cli.triage`
