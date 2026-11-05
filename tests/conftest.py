"""Shared fixtures: break the target once, then open connections to both DBs."""
import json
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest

from reconciler.constants import SOURCE_DB, SOURCE_PORT, TARGET_DB, TARGET_PORT
from reconciler.db import get_params

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ERROR_MIGRATE = PROJECT_ROOT / "scripts" / "error_migrate.py"
ANSWER_KEY = PROJECT_ROOT / "answer_key.json"


@pytest.fixture(scope="session")
def answer_key():
    """Run the clean migration + fault injection once, return the answer key.

    error_migrate.py writes answer_key.json relative to its working directory,
    so it is run from the project root. It swallows connection errors and still
    exits 0, so the written key is what proves the run actually happened.
    """
    before = ANSWER_KEY.stat().st_mtime if ANSWER_KEY.exists() else None

    subprocess.run(
        [sys.executable, str(ERROR_MIGRATE)],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    if not ANSWER_KEY.exists() or ANSWER_KEY.stat().st_mtime == before:
        pytest.fail(
            f"{ERROR_MIGRATE.name} did not write a fresh {ANSWER_KEY.name}; "
            "are both databases up?"
        )

    key = json.loads(ANSWER_KEY.read_text())
    # A fault that touched no rows would make every assertion vacuously true.
    empty = [name for name, keys in key.items() if not keys]
    if empty:
        pytest.fail(f"These faults touched no rows: {empty}")

    return key


@pytest.fixture(scope="session")
def conns(answer_key):
    """Open one connection to each database for the whole test session."""
    with psycopg.connect(**get_params(SOURCE_PORT, SOURCE_DB)) as src_conn, (
        psycopg.connect(**get_params(TARGET_PORT, TARGET_DB))
    ) as tgt_conn:
        yield src_conn, tgt_conn
