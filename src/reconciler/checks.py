from reconciler.tables import TABLES
from reconciler.db import get_params
from reconciler.constants import *
import psycopg


def check_row_counts(src_conn, tar_conn):
    for table in TABLES:
        with src_conn.cursor() as src_cur, tar_conn.cursor() as tar_cur:
            src_cur.execute(f"SELECT COUNT(*) FROM {table}")
            src_result = src_cur.fetchone()[0]
            tar_cur.execute(f"SELECT COUNT(*) FROM {table}")
            tar_result = tar_cur.fetchone()[0]

            print(
                f"{table}\tsource={src_result}\ttarget={tar_result}\t{"OK" if src_result==tar_result else "BAD"}"
            )


def check_keys(src_conn: psycopg.Connection, tar_conn):
    for table in TABLES:
        with src_conn.cursor(name="src_stream_cursor") as src_cur, tar_conn.cursor(
            name="tar_stream_cursor"
        ) as tar_cur:
            src_cur.execute(f"SELECT tconst FROM {table};")
            tar_cur.execute(f"SELECT tconst FROM {table};")
            src_keys = set()
            tar_keys = set()
            while True:
                src_result = src_cur.fetchmany(BATCH_SIZE)
                tar_result = tar_cur.fetchmany(BATCH_SIZE)

                # break only if both result sets are empty
                if not src_result and not tar_result:
                    break

                # diff.update(src_result - tar_result)
                src_keys.update(src_result)
                tar_keys.update(tar_result)

            missing_keys = src_keys - tar_keys
            extra_keys = tar_keys - src_keys
            missing_keys_count = len(missing_keys)
            extra_keys_count = len(extra_keys)

            print(
                f"{table}\tmissing_keys_count={missing_keys_count} | extra_keys_count={extra_keys_count}\t{"OK" if missing_keys_count == 0 and extra_keys_count == 0 else "BAD"}"
            )
            if missing_keys_count > 0:
                print(f"FROM {table}:missing_keys:{missing_keys}")
            if extra_keys_count > 0:
                print(f"FROM {table}:extra_keys:{missing_keys}")


def main():
    try:
        with psycopg.connect(
            **get_params(SOURCE_PORT, SOURCE_DB)
        ) as src_conn, psycopg.connect(
            **get_params(TARGET_PORT, TARGET_DB)
        ) as tar_conn:
            check_row_counts(src_conn, tar_conn)
            check_keys(src_conn, tar_conn)
    except psycopg.OperationalError as e:
        print(f"Database connection failed: {e}")


if __name__ == "__main__":
    main()
