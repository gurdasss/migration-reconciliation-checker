"""Shared fixtures: break the target once, then open connections to both DBs."""
import json
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest

from reconciler.constants import SOURCE_DB, SOURCE_HOST, TARGET_DB, TARGET_HOST
from reconciler.db import source_params, target_params

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ERROR_MIGRATE = PROJECT_ROOT / "scripts" / "error_migrate.py"
ANSWER_KEY = PROJECT_ROOT / "answer_key.json"


@pytest.fixture(scope="session")
def databases_available():
    """Skip the suite with a clear reason when the containers are not up.

    Without this, every test fails with a raw connection error instead. Change
    pytest.skip to pytest.fail if you would rather a CI run go red.
    """
    databases = (
        (SOURCE_DB, SOURCE_HOST, source_params),
        (TARGET_DB, TARGET_HOST, target_params),
    )
    for dbname, host, params in databases:
        try:
            with psycopg.connect(**params()):
                pass
        except psycopg.OperationalError as e:
            pytest.skip(
                f"cannot reach {dbname} on {host} "
                f"(try: docker compose up -d) -- {e}",
            )


@pytest.fixture(scope="session")
def answer_key(databases_available):
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
    with psycopg.connect(**source_params()) as src_conn, (
        psycopg.connect(**target_params())
    ) as tgt_conn:
        yield src_conn, tgt_conn
