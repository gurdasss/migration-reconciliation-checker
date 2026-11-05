"""Compare source and target, print the report, exit with a meaningful code.

The logic lives in reconciler.report so the same verdict is available to a
Lambda handler. This script only decides where the lines are printed.

    0  checked, and source and target agree
    1  checked, and found damage
    2  could not check (database unreachable, or no credentials)
"""
import sys

from reconciler.report import EXIT_CANNOT_CHECK, reconcile


def main() -> int:
    """Return the exit code rather than calling sys.exit, so tests can call it."""
    code, lines = reconcile()

    # Failures go to stderr, so `check.py > report.txt` still shows them.
    stream = sys.stderr if code == EXIT_CANNOT_CHECK else sys.stdout
    print(file=stream)
    for line in lines:
        print(line, file=stream)

    if code == EXIT_CANNOT_CHECK:
        print(
            "Are both databases up? (docker compose up -d)",
            file=sys.stderr,
        )

    return code


if __name__ == "__main__":
    # sys.exit is what actually sets the process exit code.
    sys.exit(main())
