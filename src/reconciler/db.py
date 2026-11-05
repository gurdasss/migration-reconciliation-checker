"""Build connection parameters for the source and target databases.

Credentials are read from the environment when they are first needed, never at
import time. Locally they come from `.env`; in AWS they are set on the Lambda
(from Secrets Manager, say). Importing this module must never fail just
because credentials are absent, or a Lambda dies at cold start before it can
report why.
"""
import os

from reconciler.constants import (
    CONNECT_TIMEOUT,
    SOURCE_DB,
    SOURCE_HOST,
    SOURCE_PORT,
    TARGET_DB,
    TARGET_HOST,
    TARGET_PORT,
)

try:  # python-dotenv is a local convenience, not a runtime requirement
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - only in a slim deployment
    load_dotenv = None

_env_file_loaded = False


def _load_env_file():
    """Read `.env` once, if python-dotenv is installed and a file exists.

    Values already set in the environment win: python-dotenv does not
    overwrite them, which is what makes the same code work in AWS.
    """
    global _env_file_loaded
    if not _env_file_loaded and load_dotenv is not None:
        load_dotenv()
        _env_file_loaded = True


def get_credentials():
    """Return (user, password), raising a clear error if either is missing."""
    _load_env_file()
    user = os.environ.get("DB_USER")
    password = os.environ.get("DB_PASSWORD")

    if not user or not password:
        missing = [
            name
            for name, value in (("DB_USER", user), ("DB_PASSWORD", password))
            if not value
        ]
        raise RuntimeError(
            f"{' and '.join(missing)} not set. Locally, put them in .env; "
            "in AWS, set them on the function's environment."
        )

    return user, password


def get_params(port, dbname, host="localhost"):
    """Return the kwargs dict for psycopg.connect()."""
    user, password = get_credentials()
    return {
        "dbname": dbname,
        "user": user,
        "password": password,
        "host": host,
        "port": port,
        "connect_timeout": CONNECT_TIMEOUT,
    }


def source_params():
    """Connection kwargs for the old system."""
    return get_params(SOURCE_PORT, SOURCE_DB, SOURCE_HOST)


def target_params():
    """Connection kwargs for the new system."""
    return get_params(TARGET_PORT, TARGET_DB, TARGET_HOST)
