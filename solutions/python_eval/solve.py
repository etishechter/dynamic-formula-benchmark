"""Python solution: computes dynamic formulas using compile()/eval().

For every formula in t_targil, the formula (and its optional condition /
false-branch) is compiled once into a code object, then evaluated once per
row of t_data in a plain Python loop. This is the "interpreted, row by row"
approach - the baseline the other two methods (C# / native SQL) are compared
against.

Usage:
    python solve.py --db ../../payments.db
"""
import argparse
import math
import sqlite3
import time

METHOD = "Python-eval"

# Restricted namespace: no builtins, only the math helpers the formulas need.
SAFE_FUNCS = {"sqrt": math.sqrt, "log": math.log, "abs": abs}


def to_python_syntax(expr: str) -> str:
    """Translates the shared formula syntax (^ for power) to Python (**)."""
    return expr.replace("^", "**")


def compile_expr(expr: str):
    return compile(to_python_syntax(expr), "<formula>", "eval")


def load_formulas(conn: sqlite3.Connection):
    cur = conn.execute("SELECT targil_id, targil, tnai, targil_false FROM t_targil")
    formulas = []
    for targil_id, targil, tnai, targil_false in cur.fetchall():
        formulas.append(
            {
                "targil_id": targil_id,
                "targil_code": compile_expr(targil),
                "tnai_code": compile_expr(tnai) if tnai else None,
                "false_code": compile_expr(targil_false) if targil_false else None,
            }
        )
    return formulas


def load_data(conn: sqlite3.Connection):
    cur = conn.execute("SELECT data_id, a, b, c, d FROM t_data")
    return cur.fetchall()


def compute(formula: dict, a: float, b: float, c: float, d: float) -> float:
    scope = {"a": a, "b": b, "c": c, "d": d}
    if formula["tnai_code"] is not None:
        condition_true = eval(formula["tnai_code"], {"__builtins__": {}, **SAFE_FUNCS}, scope)
        code = formula["targil_code"] if condition_true else formula["false_code"]
    else:
        code = formula["targil_code"]
    return eval(code, {"__builtins__": {}, **SAFE_FUNCS}, scope)


def run(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("DELETE FROM t_results WHERE method = ?", (METHOD,))
        conn.execute("DELETE FROM t_log WHERE method = ?", (METHOD,))
        conn.commit()

        formulas = load_formulas(conn)
        data_rows = load_data(conn)
        print(f"Loaded {len(formulas)} formulas and {len(data_rows):,} data rows")

        for formula in formulas:
            results = []
            start = time.perf_counter()
            for data_id, a, b, c, d in data_rows:
                result = compute(formula, a, b, c, d)
                results.append((data_id, formula["targil_id"], METHOD, result))
            elapsed = time.perf_counter() - start

            conn.executemany(
                "INSERT INTO t_results (data_id, targil_id, method, result) VALUES (?, ?, ?, ?)",
                results,
            )
            conn.execute(
                "INSERT INTO t_log (targil_id, method, run_time) VALUES (?, ?, ?)",
                (formula["targil_id"], METHOD, elapsed),
            )
            conn.commit()
            print(f"  targil_id={formula['targil_id']:>2}  rows={len(data_rows):,}  time={elapsed:.4f}s")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute formulas using Python eval")
    parser.add_argument("--db", default="../../payments.db", help="Path to the SQLite file")
    args = parser.parse_args()
    run(args.db)
