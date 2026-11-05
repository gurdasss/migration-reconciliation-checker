"""The drill-down must name the exact column each fault edited.

Each fault touches one known column, so the answer key says not just which
rows should be reported but which column should be named in each of them, and
in which direction the value moved.
"""
from reconciler.checks import explain_changed_rows


def test_movies_drilldown_names_runtime_minutes(conns, answer_key):
    src_conn, tgt_conn = conns

    expected_keys = set(answer_key["null_runtime"]) - set(answer_key["delete_movies"])
    differences = explain_changed_rows(src_conn, tgt_conn, "movies", expected_keys)

    assert set(differences) == expected_keys
    for key, columns in differences.items():
        assert set(columns) == {"runtime_minutes"}, key
        # null_runtime blanks the value, so target must be NULL
        assert columns["runtime_minutes"]["target"] is None, key
        assert columns["runtime_minutes"]["source"] is not None, key


def test_ratings_drilldown_names_the_edited_column(conns, answer_key):
    src_conn, tgt_conn = conns

    deleted = set(answer_key["delete_ratings"])
    rating_keys = set(answer_key["change_rating"]) - deleted
    votes_keys = set(answer_key["change_votes"]) - deleted

    expected = {}
    for key in rating_keys:
        expected.setdefault(key, set()).add("average_rating")
    for key in votes_keys:
        expected.setdefault(key, set()).add("num_votes")

    differences = explain_changed_rows(
        src_conn, tgt_conn, "ratings", rating_keys | votes_keys
    )

    assert {key: set(columns) for key, columns in differences.items()} == expected

    # change_rating adds 1 to the rating; change_votes subtracts 1 from the votes
    for key in rating_keys:
        values = differences[key]["average_rating"]
        assert values["target"] - values["source"] == 1, key
    for key in votes_keys:
        values = differences[key]["num_votes"]
        assert values["target"] - values["source"] == -1, key
