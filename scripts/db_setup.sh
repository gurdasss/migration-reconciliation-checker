#!/usr/bin/env bash
set -euo pipefail          # stop at the first error, don't keep going blindly

# read DB_USER and DB_PASSWORD from .env
set -a; source .env; set +a
export PGPASSWORD="$DB_PASSWORD"

SOURCE_PORT=5433
TARGET_PORT=5434

# 1. start the databases
docker compose up -d

# 2. wait until each database is ready to accept connections
for port in $SOURCE_PORT $TARGET_PORT; do
  until pg_isready -h localhost -p "$port" -U "$DB_USER" >/dev/null 2>&1; do
    sleep 1
  done
done

# 3. download and trim the data, only if we don't already have it
mkdir -p data
if [ ! -f data/movies.tsv ]; then
  cd data
  curl -fLO https://datasets.imdbws.com/title.basics.tsv.gz
  curl -fLO https://datasets.imdbws.com/title.ratings.tsv.gz
  gunzip -f title.basics.tsv.gz title.ratings.tsv.gz
  awk -F'\t' 'NR==1 || $2=="movie"' title.basics.tsv > movies.tsv
  awk -F'\t' 'NR==FNR{a[$1]; next} FNR==1 || ($1 in a)' movies.tsv title.ratings.tsv > ratings.tsv
  rm title.basics.tsv title.ratings.tsv
  cd ..
fi

# 4. create the tables in a database (empty)
create_tables() {   # usage: create_tables <port> <database>
  psql -h localhost -p "$1" -U "$DB_USER" -d "$2" -v ON_ERROR_STOP=1 -f sql/schema.sql
}

# 5. load the IMDb data into a database
load_data() {       # usage: load_data <port> <database>
  psql -h localhost -p "$1" -U "$DB_USER" -d "$2" -v ON_ERROR_STOP=1 \
    -c "\copy movies FROM 'data/movies.tsv' WITH (FORMAT csv, HEADER true, DELIMITER E'\t', QUOTE E'\b', NULL '\N')" \
    -c "\copy ratings FROM 'data/ratings.tsv' WITH (FORMAT csv, HEADER true, DELIMITER E'\t', QUOTE E'\b', NULL '\N')"
}

# source: tables + data (this is the "old system")
create_tables "$SOURCE_PORT" source
load_data     "$SOURCE_PORT" source

# target: tables only, left empty (the migration will fill it)
create_tables "$TARGET_PORT" target

echo "Done: source is loaded, target has empty tables and is ready for migration."