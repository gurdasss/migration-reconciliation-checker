from tables import TABLES
from db import get_params
from constants import *
import psycopg


def check_row_counts(src_conn: psycopg.Connection, tar_conn):
    for table in TABLES:
        with src_conn.cursor() as src_cur, tar_conn.cursor() as tar_cur:
            src_cur.execute(f"SELECT COUNT(*) FROM {table}")
            src_result = src_cur.fetchone()[0]
            tar_cur.execute(f"SELECT COUNT(*) FROM {table}")
            tar_result = tar_cur.fetchone()[0]

            print(
                f"{table}\tsource={src_result}\ttarget={tar_result}\t{"OK" if src_result==tar_result else "BAD"}"
            )


def main():
    try:
        with psycopg.connect(
            **get_params(SOURCE_PORT, SOURCE_DB)
        ) as src_conn, psycopg.connect(
            **get_params(TARGET_PORT, TARGET_DB)
        ) as tar_conn:
            check_row_counts(src_conn, tar_conn)
    except psycopg.OperationalError as e:
        print(f"Database connection failed: {e}")


if __name__ == "__main__":
    main()
