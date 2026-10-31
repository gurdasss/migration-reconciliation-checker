"""Run the clean migration, then deliberately corrupt the target database.

Every change is recorded in answer_key.json, so the checker's report can be
compared against what was actually broken.
"""
import json
from pathlib import Path

import psycopg

# Adjust these imports to match your package layout.
from reconciler.db import get_params
from reconciler.migrate import run_clean_migration

TARGET_PORT = 5434
TARGET_DB = "target"
ANSWER_KEY_PATH = Path("answer_key.json")

# Rows are chosen by hashing the key, so the same data always gives the same
# picks. The text added to the key ('del_ratings' etc.) makes each fault pick
# different rows. Each query takes one parameter: how many rows to affect.

DELETE_RATINGS = """
DELETE FROM ratings
WHERE tconst IN (
    SELECT tconst FROM ratings ORDER BY md5(tconst || 'del_ratings') LIMIT %s
)
RETURNING tconst;
"""

# Only unrated movies, so the foreign key from ratings doesn't block the delete.
DELETE_MOVIES = """
DELETE FROM movies
WHERE tconst IN (
    SELECT m.tconst
    FROM movies m
    LEFT JOIN ratings r ON r.tconst = m.tconst
    WHERE r.tconst IS NULL
    ORDER BY md5(m.tconst || 'del_movies')
    LIMIT %s
)
RETURNING tconst;
"""

# 'ttFAKE...' can never collide with a real IMDb id, which is digits only.
INSERT_FAKE_MOVIES = """
INSERT INTO movies (tconst, title_type, primary_title, original_title,
                    is_adult, start_year, end_year, runtime_minutes, genres)
SELECT 'ttFAKE' || lpad(g::text, 3, '0'), 'movie',
       'Fake Movie ' || g, 'Fake Movie ' || g,
       false, 2000 + g, NULL, 90 + g, 'Drama'
FROM generate_series(1, %s) AS g
RETURNING tconst;
"""

# IS NOT NULL: only rows that actually change, so the answer key stays honest.
NULL_RUNTIME = """
UPDATE movies SET runtime_minutes = NULL
WHERE tconst IN (
    SELECT tconst FROM movies
    WHERE runtime_minutes IS NOT NULL
    ORDER BY md5(tconst || 'null_runtime')
    LIMIT %s
)
RETURNING tconst;
"""

CHANGE_RATING = """
UPDATE ratings SET average_rating = average_rating + 1
WHERE tconst IN (
    SELECT tconst FROM ratings
    WHERE average_rating <= 9.0
    ORDER BY md5(tconst || 'chg_rating')
    LIMIT %s
)
RETURNING tconst;
"""

# A subtle, off-by-one change that is easy to miss by eye.
CHANGE_VOTES = """
UPDATE ratings SET num_votes = num_votes - 1
WHERE tconst IN (
    SELECT tconst FROM ratings
    WHERE num_votes > 1
    ORDER BY md5(tconst || 'chg_votes')
    LIMIT %s
)
RETURNING tconst;
"""

# fault name -> (query, how many rows to affect). Runs in this order.
# 5 deleted movies + 5 fake ones keeps the movies row count unchanged, so only
# the key check can catch that swap.
FAULTS = {
    "delete_ratings": (DELETE_RATINGS, 5),
    "delete_movies": (DELETE_MOVIES, 5),
    "insert_fake_movies": (INSERT_FAKE_MOVIES, 5),
    "null_runtime": (NULL_RUNTIME, 20),
    "change_rating": (CHANGE_RATING, 20),
    "change_votes": (CHANGE_VOTES, 20),
}


def inject_fault(cur: psycopg.Cursor, name: str, query: str, n: int) -> list[str]:
    """Apply one fault and return the keys it touched."""
    cur.execute(query, (n,))
    keys = [row[0] for row in cur.fetchall()]
    print(f"{name}: {len(keys)} rows")
    return keys


def main() -> None:
    try:
        # 1. Fill target correctly. It uses its own connections and commits.
        run_clean_migration()

        # 2. Corrupt target. All faults share one transaction: if any of them
        #    fails, everything rolls back and target stays clean.
        answer_key: dict[str, list[str]] = {}
        with psycopg.connect(**get_params(TARGET_PORT, TARGET_DB)) as tar_conn:
            with tar_conn.cursor() as tar_cur:
                for name, (query, n) in FAULTS.items():
                    answer_key[name] = inject_fault(tar_cur, name, query, n)
        # Leaving the with-block above committed the changes.

        # 3. Write the answer key only after the commit succeeded.
        ANSWER_KEY_PATH.write_text(json.dumps(answer_key, indent=2))
        print(f"Answer key written to {ANSWER_KEY_PATH}")

    except psycopg.OperationalError as e:
        print(f"Database connection failed: {e}")


if __name__ == "__main__":
    main()