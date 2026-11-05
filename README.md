# Migration Reconciliation Checker

After copying data from an old database to a new one, how do you know
everything arrived? This tool answers that question, and reports exactly what
is missing, duplicated, blanked or changed.

The trap it is built around: **a migration can report success, and the row
counts can match, while the data is wrong.** That case is demonstrated below
with real output.

## How it works

| Database | Role              | Port   |
| -------- | ----------------- | ------ |
| `source` | the old system    | `5433` |
| `target` | the new system    | `5434` |

The sample data is a trimmed IMDb dataset: `movies` (every title of type
`movie`) and `ratings` (the ratings for those titles).

1. Setup loads `source` and creates **empty** tables in `target`.
2. A migration copies `source` into `target`.
3. `scripts/error_migrate.py` runs that migration and then deliberately
   damages `target` in six known ways, recording every key it touched in
   `answer_key.json`.
4. The checker compares the two databases. Its findings have to match the
   answer key — and the test suite asserts exactly that, so the checker is
   graded against known damage rather than judged by eye.

The six injected faults: 5 deleted ratings, 5 deleted movies, 5 fake movies
inserted, 20 blanked runtimes, 20 altered ratings, 20 altered vote counts.

## Setup

1. Copy the example environment file and set your own credentials:
   ```bash
   cp .env.example .env     # then edit DB_USER and DB_PASSWORD
   ```
   Keep real credentials in `.env`; it is excluded from Git.
2. Install Docker, `psql` and `pg_isready` (provided by `postgresql-client`),
   `curl`, and `gzip`.
3. Create a virtual environment and install the project:
   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   pip install -e .
   ```
4. Run the setup script:
   ```bash
   ./scripts/db_setup.sh
   ```
   This starts both PostgreSQL containers, downloads and trims the IMDb data,
   loads it into `source`, and creates empty tables in `target`.

Note that `target` starts empty, so until a migration has run the checker will
correctly report every single key as missing.

## Running it

```bash
python scripts/clean_migrate.py    # copy source -> target correctly
python scripts/error_migrate.py    # copy, then inject the known faults
python scripts/check.py            # compare the two databases
pytest                             # assert the findings match the answer key
```

To see the tool actually catch something, run `error_migrate.py` and then
`check.py`.

`check.py` is the entry point for automation, so it reports its result as an
exit code:

| Code | Meaning                                        |
| ---- | ---------------------------------------------- |
| `0`  | checked, and source and target agree           |
| `1`  | checked, and found damage                      |
| `2`  | could not check (a database was unreachable)   |

`2` is deliberately not `0`: "nothing was verified" must never look like
"everything matched" to a scheduled job.

## Why one check isn't enough

The checker runs four checks, because each one is blind to something another
one catches.

| Check                                             | Catches                                 | Blind spot                                       |
| ------------------------------------------------- | --------------------------------------- | ------------------------------------------------ |
| Row counts                                        | tables of different sizes               | a swap: rows deleted and others added            |
| Key sets                                          | which rows are missing or unexpected    | rows that are present but hold wrong values      |
| NULL counts per column                            | columns that lost their values          | totals are distorted by missing and extra rows   |
| Row fingerprints, `md5(ROW(...)::text)`           | any changed or blanked value            | assumes identical column types on both sides     |

Here is the summary from a real run against the injected faults (counts come
from one IMDb download; yours will differ, since IMDb refreshes the data):

```
=== Row count check ===
  movies: source=760450, target=760450 [PASS]
  ratings: source=350579, target=350574 [FAIL]

=== Summary ===
  - movies: 5 keys missing from target (e.g. tt0819827, tt11564648, tt1513200)
  - movies: 5 unexpected keys in target (e.g. ttFAKE001, ttFAKE002, ttFAKE003)
  - movies.start_year: null counts differ (source=113771, target=113769)
  - movies.runtime_minutes: null counts differ (source=271690, target=271707)
  - movies: 20 rows have changed values (e.g. tt0014693, tt0023683, tt0083117)
  - ratings: row counts differ by -5 (source=350579, target=350574)
  - ratings: 5 keys missing from target (e.g. tt0027621, tt0064743, tt0069257)
  - ratings: 40 rows have changed values (e.g. tt0028601, tt0047946, tt0055134)

  MIGRATION NOT OK: 8 problems found.
```

Read the first two lines again: **the `movies` row counts match exactly, and
`movies` has lost 5 rows.** Five rows were deleted and five fake rows were
inserted, so the totals cancel out. A checker that only counted rows would
have declared this migration clean. The key check sees straight through it,
because it compares *which* keys exist rather than how many.

The reverse holds too. `ratings` keeps every key it should have apart from the
5 deleted ones, yet 40 of its rows hold wrong values — invisible to both the
count and the key check, and caught only by the fingerprints.

### Which column changed

The fingerprint check hashes the whole row, so on its own it can only say that
a row differs. `check.py` follows up by reading the flagged rows back and
comparing them column by column, grouped so the report stays short:

```
=== Which columns changed ===
  movies: runtime_minutes (20 rows)
      tt0014693  runtime_minutes: 60 -> None
      tt0023683  runtime_minutes: 65 -> None
      ... and 18 more
  ratings: average_rating (20 rows)
      tt0047946  average_rating: 5.4 -> 6.4
      ... and 19 more
  ratings: num_votes (20 rows)
      tt0028601  num_votes: 184 -> 183
      ... and 19 more
```

This is the difference between knowing 40 rating rows are wrong and knowing
that 20 of them have an inflated `average_rating` while 20 others lost a vote.

### Why `start_year` is in that list

Nothing touched `start_year`. It appears because NULL counts are totals over
the whole table: 2 of the 5 deleted movies happened to have no `start_year`,
so target's total dropped with them. The check is reporting a real
discrepancy, just not an interesting one.

A near miss in the same run makes the point sharper: the 5 deleted movies all
had an empty `end_year`, and the 5 fake rows each add an empty `end_year` back,
so the two cancel exactly and `end_year` is never flagged at all. The same
distortion that invented a `start_year` problem silently hid an `end_year` one.

This is the null check's blind spot made visible, and it is why the
fingerprint check exists. `runtime_minutes` in the same list *is* real damage
— 20 values blanked — but nothing in the null counts alone tells the two cases
apart.

## Tests

```bash
pytest
```

The suite runs `error_migrate.py` once, then asserts each check's findings
equal the answer key: missing keys, extra keys, changed rows, null counts and
row counts, plus a final test that a clean migration reports nothing at all.
A checker that is silent on good data matters as much as one that is loud on
bad data.

Two things to know:

- It takes around three minutes, because it performs a real migration of
  roughly a million rows.
- The last test re-runs the clean migration, which **wipes the damage**. After
  `pytest`, `answer_key.json` no longer describes the database. Run
  `scripts/error_migrate.py` again before demonstrating anything.

If the containers are not running, the suite skips with an explanation rather
than failing with connection errors.

## Connecting with `psql`

Replace `your_database_username` with your `DB_USER`:

```bash
psql -h localhost -p 5433 -U your_database_username -d source   # old system
psql -h localhost -p 5434 -U your_database_username -d target   # new system
```

Always pass `-h localhost` and `-p`. Without them `psql` tries a local socket
and fails with a confusing error.

## Known limits

- **Hash comparisons assume both databases print values the same way.** That
  holds here because the corresponding column types are identical. If a
  migration changes a column's type, normalise the values before hashing so
  equivalent data has the same representation on both sides.
- **Keys and fingerprints are held in memory.** Rows are streamed from the
  server in batches, but one entry per key is kept per table, which sets the
  practical ceiling on table size.
- **NULL counts are whole-table totals**, so missing and extra rows distort
  them, as `start_year` shows above.
- **Fault selection is deterministic** (`ORDER BY md5(tconst || '<fault>')`),
  so the same data always produces the same damage and runs are reproducible.
