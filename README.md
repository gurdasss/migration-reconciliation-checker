# Migration Reconciliation Checker

Checks source and target databases after a migration and reports missing,
duplicate, or unexpectedly empty data.

## Setup

1. Create a `.env` file in the project directory and set your database
   credentials:
   ```env
   DB_USER=your_database_username
   DB_PASSWORD=your_database_password
   ```
   Keep your real credentials in `.env`; it is excluded from Git.
2. Install Docker, `psql` and `pg_isready` (provided by `postgresql-client`),
   `curl`, and `gzip`.
3. Install the project:
   ```bash
   pip install -e .
   ```
4. Run the setup script:
   ```bash
   ./scripts/db_setup.sh
   ```
   This starts the source and target PostgreSQL databases, downloads the IMDb
   movie and rating data, and loads the data into both databases.

## Connecting with `psql`

Use the `psql` command-line client to connect to either database. Replace
`your_database_username` with the value of `DB_USER`; `psql` will prompt for
the password from `DB_PASSWORD`.

Connect to the source database:

```bash
psql -h localhost -p 5433 -U your_database_username -d source
```

Connect to the target database:

```bash
psql -h localhost -p 5434 -U your_database_username -d target
```

For any database exposed on a port, use this pattern and substitute the host,
port, username, and database name:

```bash
psql -h <host> -p <port> -U <username> -d <database>
```