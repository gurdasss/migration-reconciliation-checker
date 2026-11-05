"""Run every reconciliation check and report whether the migration is sound.

This is the runner: it holds no checking logic, only the decision about what
counts as a problem and which exit code to hand back. The checks themselves
live in reconciler.checks and return their findings as data.

Exit codes, which is the whole point of having a runner:

    0  checked, and source and target agree
    1  checked, and found damage
    2  could not check (databases unreachable)

Code 2 is deliberately not 0: "nothing was verified" must never look like
"everything matched" to a cron job, a CI pipeline or a Lambda.
"""
import sys

from psycopg import OperationalError, connect

from reconciler.checks import run_all_checks
from reconciler.constants import SOURCE_DB, SOURCE_PORT, TARGET_DB, TARGET_PORT
from reconciler.db import get_params
from reconciler.tables import TABLES

EXIT_OK = 0
EXIT_PROBLEMS = 1
EXIT_CANNOT_CHECK = 2


def summarise(findings: dict) -> list[str]:
    """Turn the findings into one line per problem.

    An empty list means source and target agree. Each check contributes its
    own kind of line, so a reader can tell apart rows that went missing, rows
    that appeared, values that were blanked and values that were edited.
    """
    problems = []

    for table in TABLES:
        counts = findings["row_counts"][table]
        if counts["source"] != counts["target"]:
            difference = counts["target"] - counts["source"]
            problems.append(
                f"{table}: row counts differ by {difference:+d} "
                f"(source={counts['source']}, target={counts['target']})"
            )

        keys = findings["keys"][table]
        if keys["missing"]:
            problems.append(
                f"{table}: {len(keys['missing'])} keys missing from target "
                f"(e.g. {', '.join(sorted(keys['missing'])[:3])})"
            )
        if keys["extra"]:
            problems.append(
                f"{table}: {len(keys['extra'])} unexpected keys in target "
                f"(e.g. {', '.join(sorted(keys['extra'])[:3])})"
            )

        for column, counts in findings["nulls"][table].items():
            problems.append(
                f"{table}.{column}: null counts differ "
                f"(source={counts['source']}, target={counts['target']})"
            )

        changed = findings["changed"][table]
        if changed:
            problems.append(
                f"{table}: {len(changed)} rows have changed values "
                f"(e.g. {', '.join(sorted(changed)[:3])})"
            )

    return problems


def main() -> int:
    """Return the exit code rather than calling sys.exit, so tests can call it."""
    try:
        with connect(**get_params(SOURCE_PORT, SOURCE_DB)) as src_conn, connect(
            **get_params(TARGET_PORT, TARGET_DB)
        ) as tgt_conn:
            findings = run_all_checks(src_conn, tgt_conn)
    except OperationalError as e:
        print(f"\nCould not run the checks: {e}", file=sys.stderr)
        print(
            "Nothing was verified. Are both databases up? (docker compose up -d)",
            file=sys.stderr,
        )
        return EXIT_CANNOT_CHECK

    problems = summarise(findings)

    print("\n=== Summary ===")
    if not problems:
        print("  MIGRATION OK: source and target agree on every check.")
        return EXIT_OK

    for problem in problems:
        print(f"  - {problem}")
    print(f"\n  MIGRATION NOT OK: {len(problems)} problems found.")
    return EXIT_PROBLEMS


if __name__ == "__main__":
    # sys.exit is what actually sets the process exit code.
    sys.exit(main())
