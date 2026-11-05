"""The fingerprint check must report exactly the rows whose values were edited.

Two subtleties the answer key does not state directly:

* change_rating and change_votes can pick the same key, so the expected set is
  their union, not 20 + 20.
* The check only looks at keys present on both sides, so keys that were deleted
  from target are subtracted. The fault ordering already prevents that overlap;
  the test does not rely on it.
"""
from reconciler.checks import check_changed


def test_changed_keys_match_answer_key(conns, answer_key):
    src_conn, tgt_conn = conns
    findings = check_changed(src_conn, tgt_conn)

    expected = {
        "movies": set(answer_key["null_runtime"]) - set(answer_key["delete_movies"]),
        "ratings": (
            set(answer_key["change_rating"]) | set(answer_key["change_votes"])
        )
        - set(answer_key["delete_ratings"]),
    }

    assert findings == expected
