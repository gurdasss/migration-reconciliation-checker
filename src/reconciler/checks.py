from psycopg import Connection, OperationalError, connect, sql

from reconciler.constants import BATCH_SIZE
from reconciler.db import source_params, target_params
from reconciler.tables import TABLES


def check_row_counts(src_conn, tgt_conn):
    """Compare row counts per table.

    Returns {table: {"source": int, "target": int}}.
    """
    print("\n=== Row count check ===")
    counts = {}
    for table in TABLES:
        with src_conn.cursor() as src_cur, tgt_conn.cursor() as tgt_cur:
            query = sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table))
            src_cur.execute(query)
            src_result = src_cur.fetchone()[0]
            tgt_cur.execute(query)
            tgt_result = tgt_cur.fetchone()[0]

            counts[table] = {"source": src_result, "target": tgt_result}

            print(
                f"  {table}: source={src_result}, target={tgt_result} "
                f"[{"PASS" if src_result == tgt_result else "FAIL"}]"
            )

    return counts


def _read_keys(conn, table, key):
    """Stream one table's key column into a set."""
    with conn.cursor(name="key_stream_cursor") as cur:
        cur.execute(
            sql.SQL("SELECT {} FROM {}").format(
                sql.Identifier(key),
                sql.Identifier(table),
            )
        )

        keys = set()
        while True:
            rows = cur.fetchmany(BATCH_SIZE)
            if not rows:
                break
            # each row is a 1-tuple, so take row[0] to store plain key values
            keys.update(row[0] for row in rows)

        return keys


def check_keys(src_conn, tgt_conn):
    """Compare key sets per table.

    Returns {table: {"missing": set, "extra": set}}, where "missing" is in
    source but not target and "extra" is in target but not source.
    """
    print("\n=== Key reconciliation check ===")
    findings = {}
    for table in TABLES:
        key = TABLES[table]["key"]
        src_keys = _read_keys(src_conn, table, key)
        tgt_keys = _read_keys(tgt_conn, table, key)

        missing_keys = src_keys - tgt_keys
        extra_keys = tgt_keys - src_keys
        missing_keys_count = len(missing_keys)
        extra_keys_count = len(extra_keys)

        findings[table] = {"missing": missing_keys, "extra": extra_keys}

        print(
            f"  {table}: missing keys={missing_keys_count}, "
            f"extra keys={extra_keys_count} "
            f"[{"PASS" if missing_keys_count == 0 and extra_keys_count == 0 else "FAIL"}]"
        )
        if missing_keys_count > 0:
            print(f"    Missing from target (keys): {missing_keys}")
        if extra_keys_count > 0:
            print(f"    Extra in target (keys): {extra_keys}")

    return findings


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
    """Compare per-column NULL counts.

    Returns {table: {column: {"source": int, "target": int}}} holding only the
    columns whose counts differ, so an empty dict per table means a clean pass.
    """
    print("\n=== Null-count check ===")
    findings = {}
    for table in TABLES:
        with src_conn.cursor() as src_cur, tgt_conn.cursor() as tgt_cur:
            src_result = count_nulls(src_cur, table, TABLES[table]["columns"])
            tgt_result = count_nulls(tgt_cur, table, TABLES[table]["columns"])
            mismatched_columns = []

            for column in TABLES[table]["columns"]:
                if src_result[column] != tgt_result[column]:
                    mismatched_columns.append(column)

            findings[table] = {
                column: {
                    "source": src_result[column],
                    "target": tgt_result[column],
                }
                for column in mismatched_columns
            }

            if not mismatched_columns:
                print(f"  {table}: null counts match for all columns [PASS]")
                continue

            print(f"  {table}: null counts differ [FAIL]")
            for column in mismatched_columns:
                print(
                    f"    {column}: source={src_result[column]}, "
                    f"target={tgt_result[column]}"
                )

    return findings


def _read_fingerprints(conn: Connection, table, key, columns):
    with conn.cursor(name="server_cur") as cur:
        key_id = sql.Identifier(key)
        cols = sql.SQL(", ").join(sql.Identifier(c) for c in columns)
        expression = sql.SQL("{}, md5(ROW({})::text)").format(key_id, cols)
        query = sql.SQL("SELECT {} FROM {}").format(expression, sql.Identifier(table))

        keys_and_hashs = {}

        cur.execute(query)

        while True:
            result = cur.fetchmany(BATCH_SIZE)

            if not result:
                break

            # each row is represented as a tuple
            # so we're fetching only two items so,
            # tuple unpacking
            for k, h in result:
                keys_and_hashs[k] = h

        return keys_and_hashs


def check_changed(src_conn, tgt_conn):
    """Find rows whose values differ, for keys present on both sides.

    Returns {table: set of changed keys}.
    """
    print("\n=== Changed-row check (row fingerprints) ===")
    findings = {}
    for table in TABLES:
        src_fp = _read_fingerprints(
            src_conn, table, TABLES[table]["key"], TABLES[table]["columns"]
        )
        tgt_fp = _read_fingerprints(
            tgt_conn, table, TABLES[table]["key"], TABLES[table]["columns"]
        )

        changed_keys = {
            k for k in src_fp.keys() & tgt_fp.keys() if src_fp[k] != tgt_fp[k]
        }

        findings[table] = changed_keys

        result = "PASS" if not changed_keys else "FAIL"
        print(f"  {table}: changed rows={len(changed_keys)} [{result}]")
        if changed_keys:
            print(f"    First five changed keys: {sorted(changed_keys)[:5]}")

    return findings


def _read_rows(conn, table, key, columns, keys):
    """Fetch full rows for the given keys as {key: {column: value}}.

    Keys are sent in batches so a long list of changed rows cannot build one
    enormous statement.
    """
    query = sql.SQL("SELECT {} FROM {} WHERE {} = ANY(%s)").format(
        sql.SQL(", ").join(sql.Identifier(c) for c in columns),
        sql.Identifier(table),
        sql.Identifier(key),
    )

    keys = list(keys)
    rows = {}
    with conn.cursor() as cur:
        for start in range(0, len(keys), BATCH_SIZE):
            cur.execute(query, (keys[start : start + BATCH_SIZE],))
            for row in cur.fetchall():
                values = dict(zip(columns, row))
                rows[values[key]] = values

    return rows


def explain_changed_rows(src_conn, tgt_conn, table, keys):
    """Say which columns differ, for rows the fingerprint check flagged.

    The fingerprint check hashes the whole row, so it reports that a row
    changed but not what changed in it. This reads both rows back and compares
    column by column.

    Returns {key: {column: {"source": value, "target": value}}}, holding only
    the columns that actually differ. Unlike the checks, this prints nothing at
    all: how much of a drill-down to show is the caller's decision.
    """
    key = TABLES[table]["key"]
    columns = TABLES[table]["columns"]

    src_rows = _read_rows(src_conn, table, key, columns, keys)
    tgt_rows = _read_rows(tgt_conn, table, key, columns, keys)

    differences = {}
    for k in src_rows.keys() & tgt_rows.keys():
        changed_columns = {
            column: {"source": src_rows[k][column], "target": tgt_rows[k][column]}
            for column in columns
            if src_rows[k][column] != tgt_rows[k][column]
        }
        if changed_columns:
            differences[k] = changed_columns

    return differences


def run_all_checks(src_conn, tgt_conn):
    """Run every check and return all findings in one dict."""
    return {
        "row_counts": check_row_counts(src_conn, tgt_conn),
        "keys": check_keys(src_conn, tgt_conn),
        "nulls": check_nulls(src_conn, tgt_conn),
        "changed": check_changed(src_conn, tgt_conn),
    }


def main():
    try:
        with connect(**source_params()) as src_conn, connect(
            **target_params()
        ) as tgt_conn:
            run_all_checks(src_conn, tgt_conn)

    except OperationalError as e:
        print(f"Database connection failed: {e}")


if __name__ == "__main__":
    main()
