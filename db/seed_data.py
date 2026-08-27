"""Fills data_t with N rows of random data (fields a, b, c, d).

Usage:
    python seed_data.py --db ../payments.db --rows 1000000
"""
import argparse
import random
import sqlite3
import time

BATCH_SIZE = 50_000


def seed_data(conn: sqlite3.Connection, rows: int, seed: int = 42) -> None:
    random.seed(seed)
    cur = conn.cursor()
    cur.execute("DELETE FROM data_t")

    # Values are kept positive (1.0 - 1000.0) so functions like log() and
    # sqrt() used in the sample formulas never hit an invalid domain.
    def random_row(data_id: int):
        return (
            data_id,
            round(random.uniform(1.0, 1000.0), 4),
            round(random.uniform(1.0, 1000.0), 4),
            round(random.uniform(1.0, 1000.0), 4),
            round(random.uniform(1.0, 1000.0), 4),
        )

    inserted = 0
    start = time.perf_counter()
    while inserted < rows:
        batch = min(BATCH_SIZE, rows - inserted)
        rows_batch = [random_row(inserted + i + 1) for i in range(batch)]
        cur.executemany(
            "INSERT INTO data_t (data_id, a, b, c, d) VALUES (?, ?, ?, ?, ?)",
            rows_batch,
        )
        conn.commit()
        inserted += batch
        print(f"  inserted {inserted:,} / {rows:,} rows")

    elapsed = time.perf_counter() - start
    print(f"Done: {rows:,} rows in {elapsed:.2f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed data_t with random rows")
    parser.add_argument("--db", default="payments.db", help="Path to the SQLite file")
    parser.add_argument("--rows", type=int, default=1000, help="Number of rows to insert")
    args = parser.parse_args()

    connection = sqlite3.connect(args.db)
    try:
        seed_data(connection, args.rows)
    finally:
        connection.close()
