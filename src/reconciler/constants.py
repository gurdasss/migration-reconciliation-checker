"""Connection settings, overridable by environment variable.

Locally the defaults point at the two Docker containers. In AWS the same code
reads the real endpoints from the Lambda's environment, so nothing has to be
edited to move between the two.
"""
import os

SOURCE_DB = os.environ.get("SOURCE_DB", "source")
SOURCE_HOST = os.environ.get("SOURCE_HOST", "localhost")
SOURCE_PORT = int(os.environ.get("SOURCE_PORT", 5433))

TARGET_DB = os.environ.get("TARGET_DB", "target")
TARGET_HOST = os.environ.get("TARGET_HOST", "localhost")
TARGET_PORT = int(os.environ.get("TARGET_PORT", 5434))

# How many rows to pull from a server-side cursor at a time.
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", 10_000))

# Fail fast rather than hang: a Lambda that waits for a database it cannot
# reach burns its whole timeout and reports nothing useful.
CONNECT_TIMEOUT = int(os.environ.get("DB_CONNECT_TIMEOUT", 10))
