"""The null-count check, including its blind spot.

Null totals are per-column counts over the whole table, so missing and extra
rows distort them: deleting a movie that already had a NULL end_year lowers
target's end_year total even though no end_year value was touched. The expected
target total for each column is therefore modelled explicitly:

    source total
      - NULLs in the rows deleted from target
      + NULLs in the fake rows added to target
      + values this fault blanked

Without that model, a test could only assert "runtime_minutes is somewhere in
the report", which would pass even if the check were badly wrong.
"""
from psycopg import sql

from reconciler.checks import check_nulls, count_nulls
from reconciler.tables import TABLES


def _null_counts_for_keys(conn, table, key, columns, keys):
    """Per-column NULL counts restricted to the given keys."""
    expressions = [
        sql.SQL("COUNT(*) FILTER (WHERE {} IS NULL)").format(sql.Identifier(column))
        for column in columns
    ]
    query = sql.SQL("SELECT {} FROM {} WHERE {} = ANY(%s)").format(
        sql.SQL(", ").join(expressions),
        sql.Identifier(table),
        sql.Identifier(key),
    )

    with conn.cursor() as cur:
        cur.execute(query, (list(keys),))
        return dict(zip(columns, cur.fetchone()))


def test_null_counts_match_answer_key(conns, answer_key):
    src_conn, tgt_conn = conns
    findings = check_nulls(src_conn, tgt_conn)

    deleted = {
        "movies": answer_key["delete_movies"],
        "ratings": answer_key["delete_ratings"],
    }
    # insert_fake_movies runs before null_runtime, so a fake row could itself
    # have been blanked. Those NULLs are already counted in the fake rows, so
    # only blanked real rows are added on top.
    blanked = {
        "movies": {
            "runtime_minutes": len(
                set(answer_key["null_runtime"])
                - set(answer_key["insert_fake_movies"])
            )
        },
        "ratings": {},
    }

    expected = {}
    for table in TABLES:
        key = TABLES[table]["key"]
        columns = TABLES[table]["columns"]

        with src_conn.cursor() as src_cur:
            source_totals = count_nulls(src_cur, table, columns)

        deleted_nulls = _null_counts_for_keys(
            src_conn, table, key, columns, deleted[table]
        )
        added_nulls = (
            _null_counts_for_keys(
                tgt_conn, table, key, columns, answer_key["insert_fake_movies"]
            )
            if table == "movies"
            else {column: 0 for column in columns}
        )

        expected[table] = {}
        for column in columns:
            expected_target = (
                source_totals[column]
                - deleted_nulls[column]
                + added_nulls[column]
                + blanked[table].get(column, 0)
            )
            if expected_target != source_totals[column]:
                expected[table][column] = {
                    "source": source_totals[column],
                    "target": expected_target,
                }

    assert findings == expected


def test_runtime_minutes_is_reported_as_losing_values(conns, answer_key):
    """The fault the check is actually meant to catch."""
    src_conn, tgt_conn = conns
    findings = check_nulls(src_conn, tgt_conn)

    assert "runtime_minutes" in findings["movies"]
    runtime = findings["movies"]["runtime_minutes"]
    assert runtime["target"] > runtime["source"]
