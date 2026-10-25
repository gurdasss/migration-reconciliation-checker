import os  # for fetching .env vars from os.environ
import psycopg  # for connecting to PostgreSQL
from dotenv import load_dotenv  # for loading .env vars

SOURCE_DB = "source"
SOURCE_PORT = 5433
TARGET_DB = "target"
TARGET_PORT = 5434

# 1. load DB_USER and DB_PASSWORD from .env
load_dotenv()  # reads .env file
db_user = os.environ.get("DB_USER")
db_pass = os.environ.get("DB_PASSWORD")

if not db_user or not db_pass:  # give informative error message
    raise KeyError("Either DB_USER or DB_PASSWORD is not in your .env file.")


# 2. open a connection to source (port 5433) and one to target (port 5434)
def get_params(port, dbname):
    # Define connection parameters
    # read env vars, validate them, return the dict for psycopg.connect(**params)
    return {
        "dbname": dbname,
        "user": db_user,
        "password": db_pass,
        "host": "localhost",
        "port": port,
    }


db_src_params = get_params(SOURCE_PORT, SOURCE_DB)
db_tar_params = get_params(TARGET_PORT, TARGET_DB)


# 3. empty the target tables (ratings first, then movies. Why that order?)
# 4. for each table, in the right order:
#       - read a batch of rows from source
#       - write that batch to target
#       - repeat until no rows are left
# 5. commit, and print how many rows were copied per table


def main():
    try:
        with psycopg.connect(**db_src_params) as src_conn, psycopg.connect(
            **db_tar_params
        ) as tar_conn:
            with tar_conn.cursor() as tar_cur:
                # first truncate all the tables from target db and
                # because ratings is referencing movies table
                # we would truncate both in a single op
                tar_cur.execute("TRUNCATE movies, ratings;")
            # automatically close the cursor object

            with src_conn.cursor() as src_cur:
                pass
        # commit changes to the database, if something goes haywire rollback recent change

    # automatically close the connection object
    except psycopg.OperationalError as e:
        print(f"Database connection failed: {e}")


if __name__ == "__main__":
    main()
