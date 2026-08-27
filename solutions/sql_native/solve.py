"""SQL solution: computes dynamic formulas natively inside SQLite.

Instead of pulling rows into the application and looping (like the Python
solution), this builds one dynamic SQL SELECT statement per formula (mirrors
EXECUTE IMMEDIATE / sp_executesql from the assignment spec - SQLite has no
stored procedures, so the "dynamic SQL" is built and executed directly) and
lets the database engine evaluate the expression for every row of t_data in
a single set-based query.

sqrt/log/power are registered as custom SQLite functions so this works
regardless of whether the local SQLite build has the math extension
compiled in; abs() is already built into SQLite.

Timing note: the measured time includes fetchall() - i.e. pulling the
computed rows back out of SQLite into Python - not just the server-side
computation. That is a deliberate methodology choice, not an oversight:
t_results needs the values in the application to be inserted, so fetching
them is a real, unavoidable cost of "using this method" here - same as
Python/C# which also have to materialize a results list before saving it.

Usage:
    python solve.py --db ../../payments.db
"""
import argparse
import math
import sqlite3
import time

from formula_translator import formula_to_sql

METHOD = "SQL-native"


def to_sql_syntax(expr: str) -> str:
    """Parses the shared formula syntax and returns the equivalent SQL text
    (handles arbitrary nesting, e.g. (a+b)^2 - see formula_translator.py)."""
    return formula_to_sql(expr)


def register_functions(conn: sqlite3.Connection) -> None:
    conn.create_function("sqrt", 1, math.sqrt)
    conn.create_function("log", 1, math.log)
    conn.create_function("power", 2, lambda x, y: x ** y)


def build_query(targil: str, tnai: str | None, targil_false: str | None) -> str:
    targil_sql = to_sql_syntax(targil)
    if tnai:
        tnai_sql = to_sql_syntax(tnai)
        false_sql = to_sql_syntax(targil_false)
        expr = f"CASE WHEN ({tnai_sql}) THEN ({targil_sql}) ELSE ({false_sql}) END"
    else:
        expr = targil_sql
    return f"SELECT data_id, ({expr}) AS result FROM t_data"


def run(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        register_functions(conn)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

        conn.execute("DELETE FROM t_results WHERE method = ?", (METHOD,))
        conn.execute("DELETE FROM t_log WHERE method = ?", (METHOD,))
        conn.commit()

        formulas = conn.execute(
            "SELECT targil_id, targil, tnai, targil_false FROM t_targil"
        ).fetchall()
        print(f"Loaded {len(formulas)} formulas")

        for targil_id, targil, tnai, targil_false in formulas:
            query = build_query(targil, tnai, targil_false)

            start = time.perf_counter()
            rows = conn.execute(query).fetchall()
            elapsed = time.perf_counter() - start

            results = [(data_id, targil_id, METHOD, result) for data_id, result in rows]
            conn.executemany(
                "INSERT INTO t_results (data_id, targil_id, method, result) VALUES (?, ?, ?, ?)",
                results,
            )
            conn.execute(
                "INSERT INTO t_log (targil_id, method, run_time) VALUES (?, ?, ?)",
                (targil_id, METHOD, elapsed),
            )
            conn.commit()
            print(f"  targil_id={targil_id:>2}  rows={len(rows):,}  time={elapsed:.4f}s")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute formulas natively in SQLite")
    parser.add_argument("--db", default="../../payments.db", help="Path to the SQLite file")
    args = parser.parse_args()
    run(args.db)
