"""Verifies that all methods produced identical results for every
(data_id, targil_id), and prints a run-time comparison summary from log_t.

The comparison itself runs as a single SQL aggregate query so it stays fast
and memory-light even at the full 1,000,000-row / 3-method scale (tens of
millions of rows in results_t) - it never pulls the whole table into Python.

Usage:
    python compare_results.py --db ../payments.db
"""
import argparse
import sqlite3
import time
from collections import defaultdict

TOLERANCE = 6  # decimal places for ROUND() when comparing floats across methods


def compare_results(conn: sqlite3.Connection) -> bool:
    start = time.perf_counter()
    total_combinations = conn.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT data_id, targil_id FROM results_t)"
    ).fetchone()[0]

    mismatches = conn.execute(
        f"""
        SELECT data_id, targil_id, COUNT(DISTINCT ROUND(result, {TOLERANCE}))
        FROM results_t
        GROUP BY data_id, targil_id
        HAVING COUNT(DISTINCT ROUND(result, {TOLERANCE})) > 1
        LIMIT 10
        """
    ).fetchall()
    mismatch_total = conn.execute(
        f"""
        SELECT COUNT(*) FROM (
            SELECT data_id, targil_id
            FROM results_t
            GROUP BY data_id, targil_id
            HAVING COUNT(DISTINCT ROUND(result, {TOLERANCE})) > 1
        )
        """
    ).fetchone()[0]
    elapsed = time.perf_counter() - start

    print(f"Checked {total_combinations:,} (data_id, targil_id) combinations in {elapsed:.2f}s")
    if mismatch_total:
        print(f"MISMATCH: {mismatch_total:,} combinations differ across methods")
        for data_id, targil_id, _ in mismatches:
            rows = conn.execute(
                "SELECT method, result FROM results_t WHERE data_id=? AND targil_id=?",
                (data_id, targil_id),
            ).fetchall()
            print(f"  data_id={data_id} targil_id={targil_id}  {dict(rows)}")
        return False

    print("OK: all methods agree on every result (within tolerance)")
    return True


def print_timing_summary(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT t.targil_id, l.method, l.run_time
        FROM log_t l
        JOIN targil_t t ON t.targil_id = l.targil_id
        ORDER BY t.targil_id, l.method
        """
    ).fetchall()

    print("\nRun-time comparison (seconds, total per formula for the whole data set):")
    by_targil = defaultdict(dict)
    for targil_id, method, run_time in rows:
        by_targil[targil_id][method] = run_time

    methods = sorted({m for v in by_targil.values() for m in v})
    header = "targil_id".ljust(10) + "".join(m.ljust(18) for m in methods)
    print(header)
    for targil_id, by_method in sorted(by_targil.items()):
        line = str(targil_id).ljust(10)
        for m in methods:
            val = by_method.get(m)
            line += (f"{val:.4f}".ljust(18) if val is not None else "-".ljust(18))
        print(line)

    print("\nTotal run time per method (sum across all formulas):")
    totals = defaultdict(float)
    for by_method in by_targil.values():
        for m, v in by_method.items():
            totals[m] += v
    for m, total in sorted(totals.items(), key=lambda kv: kv[1]):
        print(f"  {m.ljust(18)} {total:.4f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare results/timing across methods")
    parser.add_argument("--db", default="../payments.db", help="Path to the SQLite file")
    args = parser.parse_args()

    connection = sqlite3.connect(args.db)
    try:
        ok = compare_results(connection)
        print_timing_summary(connection)
        if not ok:
            raise SystemExit(1)
    finally:
        connection.close()
