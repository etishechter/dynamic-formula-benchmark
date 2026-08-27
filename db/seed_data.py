"""Fills t_data with N rows of random data (fields a, b, c, d).

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
    cur.execute("DELETE FROM t_data")

    # Values are kept positive (1.0 - 1000.0) so functions like log() and
    # sqrt() used in the sample formulas never hit an invalid domain.
    #
    # a and c are independent random floats, so "a == c" is true with
    # ~0 probability by chance - the true-branch of targil #11 (if a==c
    # then 1 else 0) would then go essentially untested across all 3
    # methods. To get real coverage of both branches, 1 in EQUAL_EVERY_N
    # rows deliberately sets c := a.
    EQUAL_EVERY_N = 200

    def random_row(data_id: int):
        a = round(random.uniform(1.0, 1000.0), 4)
        b = round(random.uniform(1.0, 1000.0), 4)
        c = a if data_id % EQUAL_EVERY_N == 0 else round(random.uniform(1.0, 1000.0), 4)
        d = round(random.uniform(1.0, 1000.0), 4)
        return (data_id, a, b, c, d)

    inserted = 0
    start = time.perf_counter()
    while inserted < rows:
        batch = min(BATCH_SIZE, rows - inserted)
        rows_batch = [random_row(inserted + i + 1) for i in range(batch)]
        cur.executemany(
            "INSERT INTO t_data (data_id, a, b, c, d) VALUES (?, ?, ?, ?, ?)",
            rows_batch,
        )
        conn.commit()
        inserted += batch
        print(f"  inserted {inserted:,} / {rows:,} rows")

    elapsed = time.perf_counter() - start
    print(f"Done: {rows:,} rows in {elapsed:.2f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed t_data with random rows")
    parser.add_argument("--db", default="payments.db", help="Path to the SQLite file")
    parser.add_argument("--rows", type=int, default=1000, help="Number of rows to insert")
    args = parser.parse_args()

    connection = sqlite3.connect(args.db)
    try:
        seed_data(connection, args.rows)
    finally:
        connection.close()
