"""Creates the SQLite database from schema.sql and seeds it with data + formulas.

Usage:
    python init_db.py --db ../payments.db --rows 1000          # small dev run
    python init_db.py --db ../payments.db --rows 1000000       # full assignment run
"""
import argparse
import sqlite3
from pathlib import Path

from seed_data import seed_data
from seed_formulas import seed_formulas

HERE = Path(__file__).parent


def init_db(db_path: str, rows: int) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        schema_sql = (HERE / "schema.sql").read_text(encoding="utf-8")
        conn.executescript(schema_sql)
        print(f"Schema created at {db_path}")

        seed_formulas(conn)

        print(f"Seeding {rows:,} rows of data...")
        seed_data(conn, rows)
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize and seed the benchmark database")
    parser.add_argument("--db", default=str(HERE.parent / "payments.db"), help="Path to the SQLite file")
    parser.add_argument("--rows", type=int, default=1000, help="Number of data_t rows to generate")
    args = parser.parse_args()

    init_db(args.db, args.rows)
