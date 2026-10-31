import psycopg

from reconciler.constants import (
    BATCH_SIZE,
    SOURCE_DB,
    SOURCE_PORT,
    TARGET_DB,
    TARGET_PORT,
)
from reconciler.db import get_params
from reconciler.tables import TABLES


def _copy_table(src_conn, tgt_cur, table, columns):
    with src_conn.cursor(name="src_stream_cursor") as src_cur:
        src_cur.execute(
            f"""
            SELECT {", ".join(columns)}
            FROM {table};
            """
        )
        total = 0
        insert_sql = (
            f"INSERT INTO {table} ({', '.join(columns)}) "
            f"VALUES ({', '.join(['%s'] * len(columns))})"
        )
        while True:
            rows = src_cur.fetchmany(BATCH_SIZE)
            if not rows:
                break
            tgt_cur.executemany(insert_sql, rows)
            total += len(rows)

        print(f"{total} numbers of rows fetched from source table")


def run_clean_migration():
    db_src_params = get_params(SOURCE_PORT, SOURCE_DB)
    db_tar_params = get_params(TARGET_PORT, TARGET_DB)

    try:
        with psycopg.connect(**db_src_params) as src_conn, psycopg.connect(
            **db_tar_params
        ) as tar_conn:
            with tar_conn.cursor() as tar_cur:
                tar_cur.execute("TRUNCATE movies, ratings;")
                for table in TABLES:
                    _copy_table(
                        src_conn,
                        tar_cur,
                        table,
                        TABLES[table]["columns"],
                    )
    except psycopg.OperationalError as e:
        print(f"Database connection failed: {e}")
