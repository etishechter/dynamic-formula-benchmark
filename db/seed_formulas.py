"""Fills t_targil with sample formulas: simple, complex (math functions) and
conditional (tnai / targil_false), as required by the assignment spec.

Formula syntax (shared by all 3 solution engines, each translates it to its
own expression syntax):
    variables : a, b, c, d        (columns of t_data)
    operators : + - * / ^ (power) > < >= <= == !=
    functions : sqrt(x)  log(x)  abs(x)

Usage:
    python seed_formulas.py --db ../payments.db
"""
import argparse
import sqlite3

# (targil, tnai, targil_false)
FORMULAS = [
    # -- simple formulas --
    ("a + b", None, None),
    ("c * 2", None, None),
    ("a - b", None, None),
    ("d / 4", None, None),
    # -- complex formulas (math functions) --
    ("8 * (b + a)", None, None),
    ("sqrt(c^2 + d^2)", None, None),
    ("log(b) + c", None, None),
    ("abs(d - b)", None, None),
    # -- conditional formulas (tnai / targil_false) --
    ("b * 2", "a > 5", "b / 2"),
    ("a + 1", "b < 10", "d - 1"),
    ("1", "a == c", "0"),
    # -- extra: conditional + complex, combined for a richer benchmark --
    ("sqrt(a^2 + b^2)", "c > d", "abs(a - b)"),
]


def seed_formulas(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("DELETE FROM t_targil")
    cur.executemany(
        "INSERT INTO t_targil (targil, tnai, targil_false) VALUES (?, ?, ?)",
        FORMULAS,
    )
    conn.commit()
    print(f"Inserted {len(FORMULAS)} formulas into t_targil")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed t_targil with sample formulas")
    parser.add_argument("--db", default="payments.db", help="Path to the SQLite file")
    args = parser.parse_args()

    connection = sqlite3.connect(args.db)
    try:
        seed_formulas(connection)
    finally:
        connection.close()
