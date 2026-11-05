"""The key check must report exactly the rows the fault injection deleted."""
from reconciler.checks import check_keys


def test_missing_keys_match_answer_key(conns, answer_key):
    src_conn, tgt_conn = conns
    findings = check_keys(src_conn, tgt_conn)

    expected = {
        "movies": set(answer_key["delete_movies"]),
        "ratings": set(answer_key["delete_ratings"]),
    }
    actual = {table: findings[table]["missing"] for table in expected}

    assert actual == expected


def test_extra_keys_match_answer_key(conns, answer_key):
    src_conn, tgt_conn = conns
    findings = check_keys(src_conn, tgt_conn)

    # Only movies gained fake rows; ratings should have no extras at all.
    expected = {
        "movies": set(answer_key["insert_fake_movies"]),
        "ratings": set(),
    }
    actual = {table: findings[table]["extra"] for table in expected}

    assert actual == expected
