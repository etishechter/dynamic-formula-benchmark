"""Unit tests for formula_translator.py (the tokenizer + recursive-descent
parser that translates the shared formula syntax into SQL text).

Two layers are covered:
  - Structural: the generated SQL string reflects the correct grouping
    (precedence, associativity, unary minus placement).
  - Behavioral: the generated SQL, executed against a real SQLite connection
    with the same custom functions solve.py registers, produces the
    numerically correct result - including the engine-specific behavior of
    edge cases like division by zero and unknown variables.

Run with:
    python -m pytest solutions/sql_native/test_formula_translator.py -v
"""
import math
import sqlite3

import pytest

from formula_translator import formula_to_sql, parse_formula


# ---------------------------------------------------------------------------
# Structural: does the parser build the tree the math actually requires?
# ---------------------------------------------------------------------------

class TestPrecedenceAndStructure:
    def test_operator_precedence(self):
        # a + b * 2  ->  * binds tighter than +
        assert formula_to_sql("a + b * 2") == "(a+(b*2))"

    def test_parentheses_override_precedence(self):
        assert formula_to_sql("(a + b) * 2") == "((a+b)*2)"

    def test_power_is_right_associative(self):
        # 2^3^2 must mean 2^(3^2) = 2^9 = 512, not (2^3)^2 = 64
        assert formula_to_sql("2^3^2") == "power(2,power(3,2))"

    def test_unary_minus_binds_looser_than_power(self):
        # -2^2 must mean -(2^2) = -4, matching Python's -2**2, not (-2)^2 = 4
        assert formula_to_sql("-2^2") == "(-power(2,2))"

    def test_unary_minus_on_power_rhs(self):
        # 2^-2 : the '-' belongs to the exponent, not a separate unary node
        assert formula_to_sql("2^-2") == "power(2,(-2))"

    def test_nested_expression_around_power(self):
        # (a+b)^2 - the parser must accept an arbitrary sub-expression as the
        # base, not just a single token (this is why formula_translator.py
        # exists instead of a regex replace).
        assert formula_to_sql("(a+b)^2") == "power((a+b),2)"

    def test_functions(self):
        assert formula_to_sql("sqrt(c^2 + d^2)") == "sqrt((power(c,2)+power(d,2)))"
        assert formula_to_sql("log(b) + c") == "(log(b)+c)"
        assert formula_to_sql("abs(d - b)") == "abs((d-b))"

    def test_comparison_operators_translate_to_sql(self):
        assert formula_to_sql("a == c") == "(a=c)"
        assert formula_to_sql("a != c") == "(a<>c)"
        assert formula_to_sql("a > 5") == "(a>5)"


# ---------------------------------------------------------------------------
# Behavioral: run the generated SQL against a real SQLite connection.
# ---------------------------------------------------------------------------

@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.create_function("sqrt", 1, math.sqrt)
    connection.create_function("log", 1, math.log)
    connection.create_function("power", 2, lambda x, y: x ** y)
    yield connection
    connection.close()


def eval_formula(conn, expr: str, a=0.0, b=0.0, c=0.0, d=0.0):
    sql = formula_to_sql(expr)
    row = conn.execute(f"SELECT {sql} FROM (SELECT ? AS a, ? AS b, ? AS c, ? AS d)", (a, b, c, d)).fetchone()
    return row[0]


class TestNumericEvaluation:
    @pytest.mark.parametrize(
        "expr,a,b,c,d,expected",
        [
            ("a + b", 3, 4, 0, 0, 7),
            ("a + b * 2", 1, 5, 0, 0, 11),          # precedence
            ("(a + b) * 2", 1, 5, 0, 0, 12),        # parens override precedence
            ("2^3^2", 0, 0, 0, 0, 512),             # right-associative power
            ("-2^2", 0, 0, 0, 0, -4),                # unary minus looser than ^
            ("sqrt(c^2 + d^2)", 0, 0, 3, 4, 5),      # 3-4-5 triangle
            ("abs(d - b)", 0, 10, 0, 3, 7),
        ],
    )
    def test_matches_hand_computed_value(self, conn, expr, a, b, c, d, expected):
        assert eval_formula(conn, expr, a, b, c, d) == pytest.approx(expected, abs=1e-9)

    def test_log_matches_math_log(self, conn):
        result = eval_formula(conn, "log(b) + c", b=math.e, c=1.0)
        assert result == pytest.approx(1.0 + 1.0, abs=1e-9)

    def test_condition_true_branch(self, conn):
        # if(a > 5, b * 2, b / 2) with a=10 -> true branch
        tnai_sql = formula_to_sql("a > 5")
        row = conn.execute(
            f"SELECT CASE WHEN ({tnai_sql}) THEN (b*2) ELSE (b/2) END "
            "FROM (SELECT 10.0 AS a, 8.0 AS b)"
        ).fetchone()
        assert row[0] == pytest.approx(16.0)

    def test_condition_false_branch(self, conn):
        tnai_sql = formula_to_sql("a > 5")
        row = conn.execute(
            f"SELECT CASE WHEN ({tnai_sql}) THEN (b*2) ELSE (b/2) END "
            "FROM (SELECT 2.0 AS a, 8.0 AS b)"
        ).fetchone()
        assert row[0] == pytest.approx(4.0)

    def test_equality_uses_floating_point_tolerance_at_comparison_layer(self, conn):
        # a==c is translated to plain SQL '=' (exact equality). This test
        # documents that behavior explicitly: it is compare_results.py
        # (ROUND(result, 6) across methods), not the formula language itself,
        # that applies floating-point tolerance - see its TOLERANCE constant.
        assert eval_formula(conn, "a == c", a=1.0, c=1.0) == 1
        assert eval_formula(conn, "a == c", a=1.0, c=1.0000001) == 0


class TestErrorCases:
    def test_invalid_syntax_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_formula("a + ")

    def test_unmatched_parenthesis_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_formula("(a + b")

    def test_unknown_character_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_formula("a & b")

    def test_disallowed_variable_fails_at_sql_execution(self, conn):
        # The parser itself doesn't restrict variable names to a/b/c/d (it
        # has no schema knowledge) - an out-of-range identifier like 'e'
        # parses fine but fails against the real table because there is no
        # such column. This documents where that formula would actually be
        # rejected in this engine.
        sql = formula_to_sql("e + a")
        assert sql == "(e+a)"
        with pytest.raises(sqlite3.OperationalError):
            conn.execute(f"SELECT {sql} FROM (SELECT 1.0 AS a)").fetchone()

    def test_division_by_zero_returns_null_not_error(self, conn):
        # SQLite's own semantics for x/0: no exception, result is NULL.
        # This differs from Python (ZeroDivisionError) and C# (Infinity/NaN)
        # - see solutions/csharp_solution tests for that side of the
        # comparison. None of the 12 seeded formulas can hit this (d/4 uses
        # a constant, non-zero divisor), but it matters for future formulas.
        result = eval_formula(conn, "a / d", a=1.0, d=0.0)
        assert result is None
