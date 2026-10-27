from reconciler.db import get_params
from reconciler.constants import *
import psycopg  # for connecting to PostgreSQL

from reconciler.tables import TABLES

MOVIES_COLUMNS = TABLES["movies"]["columns"]

RATINGS_COLUMNS = TABLES["ratings"]["columns"]


def copy_table(src_conn, tgt_cur, table, columns):
    # 4. for each table, in the right order:
    #       - read a batch of rows from source
    #       - write that batch to target
    #       - repeat until no rows are left
    with src_conn.cursor(name="src_stream_cursor") as src_cur:
        src_cur.execute(f"""
                    SELECT
                        {", ".join(columns)}
                    FROM {table};""")
        total = 0
        insert_sql = f"INSERT INTO {table} ({", ".join(columns)}) VALUES ({", ".join(["%s"] * len(columns))})"
        # print(insert_sql)
        while True:
            rows = src_cur.fetchmany(BATCH_SIZE)
            if not rows:
                break
            tgt_cur.executemany(insert_sql, rows)
            total += len(rows)

        # 5. commit, and print how many rows were copied per table
        print(f"{total} numbers of rows fetched from source table")


db_src_params = get_params(SOURCE_PORT, SOURCE_DB)
db_tar_params = get_params(TARGET_PORT, TARGET_DB)


def main():
    try:
        with psycopg.connect(**db_src_params) as src_conn, psycopg.connect(
            **db_tar_params
        ) as tar_conn:
            with tar_conn.cursor() as tar_cur:
                # 3. empty the target tables (ratings first, then movies. Why that order?)
                # first truncate all the tables from target db and
                # because ratings is referencing movies table
                # we would truncate both in a single op
                tar_cur.execute("TRUNCATE movies, ratings;")
                copy_table(src_conn, tar_cur, "movies", MOVIES_COLUMNS)
                copy_table(src_conn, tar_cur, "ratings", RATINGS_COLUMNS)

            # automatically close the cursor object

        # commit changes to the database, if something goes haywire rollback recent change

    # automatically close the connection object
    except psycopg.OperationalError as e:
        print(f"Database connection failed: {e}")


if __name__ == "__main__":
    main()
