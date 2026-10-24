# Migration Reconciliation Checker

## Docker Compose setup

Docker Compose starts two PostgreSQL 16 databases:

- `source_db` creates a database named `source`, available on `localhost:5433`.
- `target_db` creates a database named `target`, available on `localhost:5434`.

Both databases use the same username and password. Before starting them, create
a `.env` file in the project directory with the values referenced in
`docker-compose.yml`:

```env
DB_USER=your_database_username
DB_PASSWORD=your_database_password
```

Keep your real credentials in `.env`; it is excluded from Git.

Start the databases with:

```bash
docker compose up -d
```

Stop them with:

```bash
docker compose down
```

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