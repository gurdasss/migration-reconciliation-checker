"""A correct migration must produce no findings at all.

This file is named to sort last: it re-runs the clean migration and so wipes
the damage every other test depends on.
"""
from reconciler.checks import run_all_checks
from reconciler.migrate import run_clean_migration
from reconciler.tables import TABLES


def test_clean_migration_reports_no_findings(conns):
    src_conn, tgt_conn = conns

    # Earlier reads left both connections in an open transaction holding
    # ACCESS SHARE locks. TRUNCATE needs ACCESS EXCLUSIVE, so without ending
    # those transactions the migration below would block until the session
    # ended. Rolling back releases the locks and starts a fresh snapshot.
    src_conn.rollback()
    tgt_conn.rollback()

    run_clean_migration()

    findings = run_all_checks(src_conn, tgt_conn)

    for table in TABLES:
        counts = findings["row_counts"][table]
        assert counts["source"] == counts["target"]
        assert findings["keys"][table] == {"missing": set(), "extra": set()}
        assert findings["nulls"][table] == {}
        assert findings["changed"][table] == set()
