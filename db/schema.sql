-- Schema for the dynamic formula benchmark project (SQLite)
-- Matches the table structures defined in the assignment spec.

DROP TABLE IF EXISTS t_log;
DROP TABLE IF EXISTS t_results;
DROP TABLE IF EXISTS t_targil;
DROP TABLE IF EXISTS t_data;

-- 1. t_data - random source data. Fields a,b,c,d are the variables formulas operate on.
CREATE TABLE t_data (
    data_id INTEGER PRIMARY KEY,
    a REAL NOT NULL,
    b REAL NOT NULL,
    c REAL NOT NULL,
    d REAL NOT NULL
);

-- 2. t_targil - dynamic formula definitions.
--    targil        : the formula to compute, e.g. "8*(b+a)"
--    tnai          : optional condition, e.g. "a > 5" (NULL for unconditional formulas)
--    targil_false  : formula to use when tnai evaluates to false (NULL when tnai is NULL)
CREATE TABLE t_targil (
    targil_id INTEGER PRIMARY KEY,
    targil VARCHAR NOT NULL,
    tnai VARCHAR,
    targil_false VARCHAR
);

-- 3. t_results - computed result of every (data row x formula x method).
CREATE TABLE t_results (
    resultsl_id INTEGER PRIMARY KEY,
    data_id INTEGER NOT NULL REFERENCES t_data(data_id),
    targil_id INTEGER NOT NULL REFERENCES t_targil(targil_id),
    method VARCHAR NOT NULL,
    result REAL
);

CREATE INDEX idx_results_lookup ON t_results (targil_id, method, data_id);

-- 4. t_log - total run time to evaluate one formula, with one method, across the whole t_data table.
CREATE TABLE t_log (
    log_id INTEGER PRIMARY KEY,
    targil_id INTEGER NOT NULL REFERENCES t_targil(targil_id),
    method VARCHAR NOT NULL,
    run_time REAL
);
