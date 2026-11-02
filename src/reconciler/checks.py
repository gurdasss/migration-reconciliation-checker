from reconciler.tables import TABLES
from reconciler.db import get_params
from reconciler.constants import *
from psycopg import sql, connect, OperationalError


def check_row_counts(src_conn, tgt_conn):
    for table in TABLES:
        with src_conn.cursor() as src_cur, tgt_conn.cursor() as tgt_cur:
            src_cur.execute(f"SELECT COUNT(*) FROM {table}")
            src_result = src_cur.fetchone()[0]
            tgt_cur.execute(f"SELECT COUNT(*) FROM {table}")
            tgt_result = tgt_cur.fetchone()[0]

            print(
                f"{table}\tsource={src_result}\ttgtget={tgt_result}\t{"OK" if src_result==tgt_result else "BAD"}"
            )


def check_keys(src_conn, tgt_conn):
    for table in TABLES:
        with src_conn.cursor(name="src_stream_cursor") as src_cur, tgt_conn.cursor(
            name="tgt_stream_cursor"
        ) as tgt_cur:
            src_cur.execute(f"SELECT tconst FROM {table};")
            tgt_cur.execute(f"SELECT tconst FROM {table};")
            src_keys = set()
            tgt_keys = set()
            while True:
                src_result = src_cur.fetchmany(BATCH_SIZE)
                tgt_result = tgt_cur.fetchmany(BATCH_SIZE)

                # break only if both result sets are empty
                if not src_result and not tgt_result:
                    break

                # diff.update(src_result - tgt_result)
                src_keys.update(src_result)
                tgt_keys.update(tgt_result)

            missing_keys = src_keys - tgt_keys
            extra_keys = tgt_keys - src_keys
            missing_keys_count = len(missing_keys)
            extra_keys_count = len(extra_keys)

            print(
                f"{table}\tmissing_keys_count={missing_keys_count} | extra_keys_count={extra_keys_count}\t{"OK" if missing_keys_count == 0 and extra_keys_count == 0 else "BAD"}"
            )
            if missing_keys_count > 0:
                print(f"FROM {table}:missing_keys:{missing_keys}")
            if extra_keys_count > 0:
                print(f"FROM {table}:extra_keys:{missing_keys}")


def count_nulls(cur, table, columns):
    expressions = [
        sql.SQL("COUNT(*) FILTER (WHERE {} IS NULL)").format(sql.Identifier(column))
        for column in columns
    ]
    query = sql.SQL("SELECT {} FROM {}").format(
        sql.SQL(", ").join(expressions),
        sql.Identifier(table),
    )

    cur.execute(query)
    return dict(zip(columns, cur.fetchone()))


def check_nulls(src_conn, tgt_conn):
    for table in TABLES:
        with src_conn.cursor() as src_cur, tgt_conn.cursor() as tgt_cur:
            src_result = count_nulls(src_cur, table, TABLES[table]["columns"])
            tgt_result = count_nulls(tgt_cur, table, TABLES[table]["columns"])
            print(f"Result set from {table}:")

            for column in TABLES[table]["columns"]:
                if (
                    src_result[column] == 0
                    and tgt_result[column] == 0
                    or (src_result[column] == tgt_result[column])
                ):
                    continue
                print(
                    f"  {column}: source={src_result[column]}, "
                    f"target={tgt_result[column]}"
                )


def main():
    try:
        with connect(**get_params(SOURCE_PORT, SOURCE_DB)) as src_conn, connect(
            **get_params(TARGET_PORT, TARGET_DB)
        ) as tgt_conn:
            # check_row_counts(src_conn, tgt_conn)
            # check_keys(src_conn, tgt_conn)
            check_nulls(src_conn, tgt_conn)
    except OperationalError as e:
        print(f"Database connection failed: {e}")


if __name__ == "__main__":
    main()
