"""Row counts must differ by exactly the rows the faults removed and added.

movies loses 5 and gains 5 fake rows, so its counts match despite the damage:
this is the blind spot that makes the key check necessary.
"""
from reconciler.checks import check_row_counts


def test_row_counts_match_answer_key(conns, answer_key):
    src_conn, tgt_conn = conns
    counts = check_row_counts(src_conn, tgt_conn)

    expected_target = {
        "movies": (
            counts["movies"]["source"]
            - len(answer_key["delete_movies"])
            + len(answer_key["insert_fake_movies"])
        ),
        "ratings": counts["ratings"]["source"] - len(answer_key["delete_ratings"]),
    }
    actual_target = {table: counts[table]["target"] for table in expected_target}

    assert actual_target == expected_target


def test_movies_row_count_hides_the_swap(conns, answer_key):
    """A deliberate demonstration of the row-count blind spot."""
    src_conn, tgt_conn = conns
    counts = check_row_counts(src_conn, tgt_conn)

    assert len(answer_key["delete_movies"]) == len(answer_key["insert_fake_movies"])
    assert counts["movies"]["source"] == counts["movies"]["target"]
