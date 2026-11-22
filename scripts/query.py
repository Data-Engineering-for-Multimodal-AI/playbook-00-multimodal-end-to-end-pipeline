#!/usr/bin/env python3
"""
Query the pipeline's SQLite store (stage 6) with any SQL.

    python scripts/query.py                                   # the action plans, approved and blocked
    python scripts/query.py "SELECT * FROM rejected_readings"
    python scripts/query.py --db output/own/resolve.db "SELECT ..."

Tables: historical_baselines, rejected_readings, fused_records, action_plans.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "output" / "fixture" / "out" / "resolve.db"
DEFAULT_SQL = "SELECT ts, action, rule, status, detail FROM action_plans ORDER BY ts"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sql", nargs="?", default=DEFAULT_SQL)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="default: the store make run writes")
    args = parser.parse_args(argv)
    if not args.db.exists():
        print(f"{args.db} doesn't exist yet: make run")
        return 1
    db = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)    # read-only
    try:
        cursor = db.execute(args.sql)
    except sqlite3.Error as e:
        print(f"SQL error: {e}")
        return 1
    columns = [c[0] for c in cursor.description or []]
    rows = [["" if v is None else str(v) for v in row] for row in cursor.fetchall()]
    widths = [min(60, max([len(c)] + [len(r[i]) for r in rows])) for i, c in enumerate(columns)]
    print("  ".join(c.ljust(w) for c, w in zip(columns, widths)))
    for row in rows:
        print("  ".join(v[:w].ljust(w) for v, w in zip(row, widths)))
    print(f"({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
