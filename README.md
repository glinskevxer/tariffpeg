# tariffpeg

Guest review evidence for an accommodation standards unit.

The unit licenses serviced accommodation. Every licence carries a **schedule of
particulars**: the claims the operator registered when they applied. There is a
lift. Breakfast is in the rate. The shore is two hundred metres away. Guests
write about those same things on booking channels, in public, in their own
words.

`tariffpeg` harvests that writing under a documented fetch policy, sets it
against the particulars, and decides which licences need an inspector sent out.
It is built so that every sentence it quotes can be answered for: the digest of
the bytes that were served, the instant they were served, and the profile
version that read them travel with the quotation into the case file.

## What it does, in order

1. **Plans** a harvest from the shortfall in the statutory sample, not from the
   register. A licence that is already properly sampled is not visited.
2. **Reads** each channel under the terms agreed with it: its robots file, a
   crawl delay, a courtesy window and a daily ceiling. Nothing reaches the
   network unless it is asked to.
3. **Extracts** reviews with a profile written in a file, and says when a
   profile has stopped working rather than reporting a property with no reviews.
4. **Redacts** the personal data on the way in. The store never holds the name.
5. **Deduplicates** syndicated copies, so one guest counts once towards the
   sample and once towards corroboration.
6. **Compares** what guests said against the particulars, weighing each finding
   by whether it describes a feature or an incident, and by how old it is.
7. **Decides**, and holds the decision at a desk enquiry while the sample is
   short, because an operator will ask what else was looked at.
8. **Books** a visit on a day the premises is open and an inspector is free.

## Getting started

```
pip install -e ".[dev]" -c constraints.txt

tariffpeg --db evidence.sqlite3 db migrate
tariffpeg --db evidence.sqlite3 channel add seaboard \
    --name "Seaboard Stays" --url https://seaboard.example
tariffpeg --db evidence.sqlite3 licence add 4021 \
    --name "The Anchor Rooms" --operator "Pellow and Daughter" \
    --locality Porthgwarra --from 2025-04-01 --to 2026-03-31 \
    --particular grading_band=3 --particular let_rooms=9 \
    --particular bed_spaces=18 --particular lift=yes
tariffpeg --db evidence.sqlite3 listing add L-004021-M seaboard \
    --path /property/anchor-rooms/reviews --property-ref P-88213
tariffpeg --db evidence.sqlite3 harvest plan
tariffpeg --db evidence.sqlite3 harvest run --profiles profiles.toml --live
tariffpeg --db evidence.sqlite3 case show L-004021-M
```

Every command explains itself with `--help`, and every refusal exits with a code
that says which kind it was.

## The documents

These are written out of the code by the generators in `tariffpeg.tools`, and
the pipeline fails if any of them has drifted.

- [docs/architecture.md](docs/architecture.md), the layers and what may import what.
- [docs/commands.md](docs/commands.md), every command and every option.
- [docs/glossary.md](docs/glossary.md), the particulars and every vocabulary.
- [docs/operations.md](docs/operations.md), the runbook, with every threshold read off a constant.
- [docs/rules.md](docs/rules.md), the rule pack as an inspector reads it in a hearing.
- [docs/schema.md](docs/schema.md), every table and index, out of the migrations.

## Running the gates

```
./check.sh
```

That is the lint, the types, every self check, every generated document, the
whole suite and the end to end smoke run. The pipeline runs the same list, and
`python -m tariffpeg.tools.check_gate` fails if the two ever disagree.

Before a version goes out:

```
python -m tariffpeg.tools.release_check --verbose
```

## Notes for anybody changing this

- The layers only import downwards. `python -m tariffpeg.tools.check_layers`
  is the definition, and `docs/architecture.md` is that definition printed.
- Migrations are frozen in `migrations.lock`. Add one, then run
  `python -m tariffpeg.tools.check_migrations --write`.
- Nothing in the suite reaches the network. A test that needs a page uses a
  recorded bundle.
- Test names say what is supposed to be true, so a red line is already a
  sentence about what broke.
