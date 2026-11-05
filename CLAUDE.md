# Migration Reconciliation Checker

A tool that answers one question: after copying data from an old database (`source`) to a new one (`target`), did everything arrive correctly? Sample data is a trimmed IMDb movie dataset (`movies`, `ratings`). A deliberately buggy migration produces known damage, and the checker has to find all of it.

## How the project works

1. `source` is the old system, loaded with IMDb data. `target` is the new system and starts with empty tables.
2. `clean_migrate.py` copies `source` to `target` correctly.
3. `error_migrate.py` runs the clean migration, then corrupts `target` in known ways (missing rows, fake extra rows, blanked values, changed values) and writes every touched key to `answer_key.json`.
4. The checker compares the two databases. Its findings must match `answer_key.json`.

## Development environment

- Runs inside **WSL2 (Ubuntu)** on Windows. Do all project work in the WSL terminal, not in Windows.
- **Python 3.12**, in a virtual environment at `.venv` in the project root.
- **Docker + Docker Compose** run two PostgreSQL 16 containers.
- Postgres client tools (`psql`, `pg_isready`) are installed in WSL (`postgresql-client`). There is no Postgres server installed in WSL itself.
- Dependencies: `psycopg[binary]`, `python-dotenv`, `pytest`. The project itself is installed in editable mode so `import reconciler` works from anywhere.

### First-time setup

```bash
cp .env.example .env            # then edit .env and set DB_USER / DB_PASSWORD
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .                # makes `import reconciler` work (package lives in src/)
./scripts/db_setup.sh           # starts both DBs, downloads IMDb data, loads source, creates empty target tables
```

### Every new terminal session

```bash
cd ~/migration-reconciliation-checker
source .venv/bin/activate

# load credentials from .env into this shell
set -a; source .env; set +a

# let psql use the password without prompting (this shell only, never save it in a file)
export PGPASSWORD="$DB_PASSWORD"
```

### Databases

| Database | Host        | Port   | Container   |
| -------- | ----------- | ------ | ----------- |
| `source` | `localhost` | `5433` | `source_db` |
| `target` | `localhost` | `5434` | `target_db` |

The user and password come from `.env` (`DB_USER`, `DB_PASSWORD`). Connect with:

```bash
psql -h localhost -p 5433 -U "$DB_USER" -d source
psql -h localhost -p 5434 -U "$DB_USER" -d target
```

Always pass `-h localhost` and `-p`. Without them `psql` tries a local socket and fails with confusing errors.

### Credentials rules

- Credentials live only in `.env`, which is gitignored. Commit `.env.example` with placeholder values.
- Never hardcode a password, put one in a URL string, or commit one. Python reads them with `python-dotenv` (`load_dotenv()`, then `os.environ`).
- `PGPASSWORD` is exported per shell session only.
- The container's user and password are created **only the first time** a container starts. After changing `.env`, reset with `docker compose down -v && docker compose up -d` (the `-v` deletes the stored data, which holds the old credentials).

## Common commands

```bash
docker compose up -d                       # start both databases
docker compose ps                          # check they are running and which ports
docker compose logs source_db | tail -n 20 # server-side reason when a connection fails
docker compose down -v                     # stop and delete containers AND data (full reset)

./scripts/db_setup.sh                      # rebuild: load source, empty target tables
python scripts/clean_migrate.py            # correct copy source -> target
python scripts/error_migrate.py             # clean migration, then inject known faults + write answer_key.json
python src/reconciler/checks.py            # run the checks (replace with scripts/check.py when it exists)
pytest                                     # run tests
```

## Layout

```
scripts/        db_setup.sh, clean_migrate.py, error_migrate.py
sql/            schema.sql  (DROP IF EXISTS + CREATE TABLE, so reruns are safe)
src/reconciler/ the importable package: tables.py (TABLES), checks.py, shared helpers
tests/
data/           downloaded IMDb files (gitignored)
```

## Code conventions

- **`TABLES` in `src/reconciler/tables.py` is the single source of truth** for table names, key column and column lists. Migration, fault injection and checks all loop over it. Never retype column lists elsewhere.
- **Name columns explicitly** in SELECT and INSERT. Never rely on `SELECT *` or column order.
- **Build SQL with `psycopg.sql`** (`sql.SQL`, `sql.Identifier`, `sql.SQL(", ").join(...)`) for table and column names. Use `%s` placeholders for values. No f-strings with anything that could be user input. Everything passed to `.format()` must be a `Composable`, not a plain string.
- **Read big tables with named (server-side) cursors** and `fetchmany(BATCH_SIZE)`, looping until an empty list comes back.
- **Check functions return their findings as data.** They also print a human-readable report as they go, but callers must never parse that text: tests and exit codes use the returned values. `run_all_checks()` bundles all four results into one dict.
- **Compare by key, never by row position.** Without `ORDER BY`, row order is not guaranteed and differs between the two databases.
- **One transaction per logical job.** Connect with `with psycopg.connect(...)`: leaving the block commits, an exception rolls back. Do not catch errors inside helpers (a failed statement aborts the transaction). Catch `psycopg.OperationalError` once, in `main()`.
- **Order matters for foreign keys:** INSERT parent first (`movies`, then `ratings`); DELETE child first; `TRUNCATE ratings, movies` in one statement, any order.
- `fetchone()` / `fetchall()` only after statements that return rows (`SELECT`, or `... RETURNING`). `TRUNCATE`, plain `INSERT`/`UPDATE`/`DELETE` return no rows.
- Fault selection is deterministic: `ORDER BY md5(tconst || '<fault name>')`, not `random()`.

## The checks, and what each one catches

| Check                                                                        | Catches                                          | Blind spot                                     |
| ---------------------------------------------------------------------------- | ------------------------------------------------ | ---------------------------------------------- |
| Row counts                                                                   | tables differ in size                            | a swap (rows deleted and different rows added) |
| Key sets (missing / extra)                                                   | which keys are missing or extra, including swaps | changed values                                 |
| NULL counts per column                                                       | columns that lost values                         | totals are distorted by missing/extra rows     |
| Row fingerprints (`md5(ROW(...)::text)`) over keys present on **both** sides | any changed or blanked value                     | needs identical column types on both sides     |

Later checks deliberately ignore keys already reported as missing or extra, so each kind of damage is reported once.

## Gotchas learned the hard way

- **"password authentication failed" can mean the user doesn't exist.** The client message is vague on purpose; `docker compose logs <service>` shows the real reason. Check the container's actual user with `docker compose exec source_db env | grep POSTGRES`.
- Row counts matching does not mean the data matches.
- IMDb files are refreshed regularly, so exact row counts differ between fresh downloads. Never hardcode counts; use the answer key.
- A freshly set-up machine has an **empty target**: the checker will report every key as missing until the migration has run.
- Do not commit `data/`, `.env`, or `answer_key.json`.

## How to work with me on this project

Gurdas is building this to learn, and will present it. Explain concepts in simple words, give the idea plus a skeleton, and let him write the code unless he explicitly asks for the full version. When he asks for something to be written, write it. Point out bugs and gaps directly, even if the output looks fine, and verify claims against the answer key rather than by eye.

## Planned next steps

1. ~~pytest test: run `error_migrate.py`, run the checks, assert findings equal `answer_key.json`.~~ **Done** — `tests/` covers missing keys, extra keys, changed rows, null counts, row counts and the clean case.
2. `scripts/check.py`: one runner that runs all checks, prints a short report and exits non-zero on any mismatch; also test the clean case.
3. README: problem, run order, "why one check isn't enough" using real results, known limits (keys held in memory, identical column types assumed).
4. Optional drill-down: for changed keys, show which column differs.
5. AWS stage: run the checker as a Lambda against RDS, results in CloudWatch.
