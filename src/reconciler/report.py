"""Turn findings into a verdict: report lines plus an exit code.

This lives in the package rather than in the runner script so that anything
can reach it -- the CLI, a test, or a Lambda handler. Nothing here prints:
callers decide where the lines go, which for a Lambda is the log and for the
CLI is stdout.

Exit codes:

    0  checked, and source and target agree
    1  checked, and found damage
    2  could not check (database unreachable, or no credentials)

Code 2 is deliberately not 0: "nothing was verified" must never look like
"everything matched" to a scheduled job.
"""
from psycopg import OperationalError, connect

from reconciler.checks import explain_changed_rows, run_all_checks
from reconciler.db import MissingCredentials, source_params, target_params
from reconciler.tables import TABLES

EXIT_OK = 0
EXIT_PROBLEMS = 1
EXIT_CANNOT_CHECK = 2

EXAMPLES_SHOWN = 3


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
                f"(e.g. {', '.join(sorted(keys['missing'])[:EXAMPLES_SHOWN])})"
            )
        if keys["extra"]:
            problems.append(
                f"{table}: {len(keys['extra'])} unexpected keys in target "
                f"(e.g. {', '.join(sorted(keys['extra'])[:EXAMPLES_SHOWN])})"
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
                f"(e.g. {', '.join(sorted(changed)[:EXAMPLES_SHOWN])})"
            )

    return problems


def changed_column_lines(src_conn, tgt_conn, findings: dict) -> list[str]:
    """Name the columns that changed, for the rows flagged as changed.

    The fingerprint check can only say that a row differs. This turns
    "20 rows have changed values" into a named column and a before/after pair,
    which is what someone fixing the migration actually needs.
    """
    if not any(findings["changed"][table] for table in TABLES):
        return []

    lines = []
    for table in TABLES:
        keys = findings["changed"][table]
        if not keys:
            continue

        differences = explain_changed_rows(src_conn, tgt_conn, table, keys)

        # Group by the set of columns that changed, so a report over many rows
        # stays short when the same column changed in all of them.
        by_columns: dict[tuple, list] = {}
        for key in differences:
            by_columns.setdefault(tuple(sorted(differences[key])), []).append(key)

        for columns, affected in sorted(by_columns.items()):
            lines.append(f"{table}: {', '.join(columns)} ({len(affected)} rows)")
            for key in sorted(affected)[:EXAMPLES_SHOWN]:
                for column, values in sorted(differences[key].items()):
                    lines.append(
                        f"    {key}  {column}: "
                        f"{values['source']} -> {values['target']}"
                    )
            if len(affected) > EXAMPLES_SHOWN:
                lines.append(f"    ... and {len(affected) - EXAMPLES_SHOWN} more")

    return lines


def reconcile() -> tuple[int, list[str]]:
    """Connect, run every check, and return (exit code, report lines).

    This is the whole job in one call, for a CLI or a Lambda handler alike.
    """
    try:
        with connect(**source_params()) as src_conn, connect(
            **target_params()
        ) as tgt_conn:
            findings = run_all_checks(src_conn, tgt_conn)
            # Inside the with-block: the drill-down needs these connections.
            detail = changed_column_lines(src_conn, tgt_conn, findings)
    except (OperationalError, MissingCredentials) as e:
        return EXIT_CANNOT_CHECK, [
            f"Could not run the checks: {e}",
            "Nothing was verified.",
        ]

    problems = summarise(findings)

    lines = []
    if detail:
        lines.append("=== Which columns changed ===")
        lines.extend(f"  {line}" for line in detail)

    lines.append("=== Summary ===")
    if not problems:
        lines.append("  MIGRATION OK: source and target agree on every check.")
        return EXIT_OK, lines

    lines.extend(f"  - {problem}" for problem in problems)
    lines.append(f"  MIGRATION NOT OK: {len(problems)} problems found.")
    return EXIT_PROBLEMS, lines
