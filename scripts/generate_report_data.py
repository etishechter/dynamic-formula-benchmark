"""Reads log_t / targil_t / results_t and writes a summary JSON file that the
Angular report screen (report/) reads directly - no backend server needed.

Usage:
    python generate_report_data.py --db ../payments.db --out ../report/public/report-data.json
"""
import argparse
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone


def build_report(conn: sqlite3.Connection) -> dict:
    formulas = {
        row[0]: {"targil_id": row[0], "targil": row[1], "tnai": row[2], "false_targil": row[3]}
        for row in conn.execute("SELECT targil_id, targil, tnai, false_targil FROM targil_t")
    }

    log_rows = conn.execute(
        "SELECT targil_id, method, run_time FROM log_t ORDER BY targil_id, method"
    ).fetchall()

    per_formula = defaultdict(dict)
    totals = defaultdict(float)
    row_counts = defaultdict(int)

    data_row_count = conn.execute("SELECT COUNT(*) FROM data_t").fetchone()[0]

    for targil_id, method, run_time in log_rows:
        per_formula[targil_id][method] = run_time
        totals[method] += run_time
        row_counts[method] += 1

    methods = sorted({m for row in log_rows for m in [row[1]]})

    formula_summaries = []
    for targil_id, by_method in sorted(per_formula.items()):
        f = formulas.get(targil_id, {})
        formula_summaries.append(
            {
                "targilId": targil_id,
                "targil": f.get("targil"),
                "tnai": f.get("tnai"),
                "falseTargil": f.get("false_targil"),
                "kind": "conditional" if f.get("tnai") else "unconditional",
                "times": by_method,
            }
        )

    mismatch_count = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT data_id, targil_id, COUNT(DISTINCT ROUND(result, 6)) AS distinct_results
            FROM results_t
            GROUP BY data_id, targil_id
            HAVING distinct_results > 1
        )
        """
    ).fetchone()[0]

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "dataRowCount": data_row_count,
        "methods": methods,
        "totalsByMethod": dict(totals),
        "formulas": formula_summaries,
        "resultsMismatchCount": mismatch_count,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate report-data.json for the Angular report screen")
    parser.add_argument("--db", default="../payments.db", help="Path to the SQLite file")
    parser.add_argument("--out", default="../report/public/report-data.json", help="Output JSON path")
    args = parser.parse_args()

    connection = sqlite3.connect(args.db)
    try:
        report = build_report(connection)
    finally:
        connection.close()

    import os
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Wrote {args.out}")
