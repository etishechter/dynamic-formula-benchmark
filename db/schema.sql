-- Schema for the dynamic formula benchmark project (SQLite)
-- Matches the table structures defined in the assignment spec.

DROP TABLE IF EXISTS log_t;
DROP TABLE IF EXISTS results_t;
DROP TABLE IF EXISTS targil_t;
DROP TABLE IF EXISTS data_t;

-- 1. data_t - random source data. Fields a,b,c,d are the variables formulas operate on.
CREATE TABLE data_t (
    data_id INTEGER PRIMARY KEY,
    a REAL NOT NULL,
    b REAL NOT NULL,
    c REAL NOT NULL,
    d REAL NOT NULL
);

-- 2. targil_t - dynamic formula definitions.
--    targil        : the formula to compute, e.g. "8*(b+a)"
--    tnai          : optional condition, e.g. "a > 5" (NULL for unconditional formulas)
--    false_targil  : formula to use when tnai evaluates to false (NULL when tnai is NULL)
CREATE TABLE targil_t (
    targil_id INTEGER PRIMARY KEY,
    targil VARCHAR NOT NULL,
    tnai VARCHAR,
    false_targil VARCHAR
);

-- 3. results_t - computed result of every (data row x formula x method).
CREATE TABLE results_t (
    resultsl_id INTEGER PRIMARY KEY,
    data_id INTEGER NOT NULL REFERENCES data_t(data_id),
    targil_id INTEGER NOT NULL REFERENCES targil_t(targil_id),
    method VARCHAR NOT NULL,
    result REAL
);

CREATE INDEX idx_results_lookup ON results_t (targil_id, method, data_id);

-- 4. log_t - total run time to evaluate one formula, with one method, across the whole data_t table.
CREATE TABLE log_t (
    log_id INTEGER PRIMARY KEY,
    targil_id INTEGER NOT NULL REFERENCES targil_t(targil_id),
    method VARCHAR NOT NULL,
    run_time REAL
);
