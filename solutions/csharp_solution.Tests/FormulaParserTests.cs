using System;
using SolveCSharp;
using Xunit;

namespace SolveCSharp.Tests;

/// <summary>
/// Unit tests for FormulaParser/Node (Formula.cs) - the hand-written
/// tokenizer + recursive-descent parser + AST evaluator used by the C#
/// solution. Mirrors solutions/sql_native/test_formula_translator.py so the
/// two custom parsers are held to the same set of precedence/associativity
/// cases.
/// </summary>
public class FormulaParserTests
{
    private static double Eval(string expr, double a = 0, double b = 0, double c = 0, double d = 0)
        => FormulaParser.Parse(expr).Eval(a, b, c, d);

    [Fact]
    public void OperatorPrecedence_MultiplicationBeforeAddition()
    {
        // a + b * 2
        Assert.Equal(11, Eval("a + b * 2", a: 1, b: 5));
    }

    [Fact]
    public void Parentheses_OverridePrecedence()
    {
        Assert.Equal(12, Eval("(a + b) * 2", a: 1, b: 5));
    }

    [Fact]
    public void Power_IsRightAssociative()
    {
        // 2^3^2 must be 2^(3^2) = 512, not (2^3)^2 = 64
        Assert.Equal(512, Eval("2^3^2"));
    }

    [Fact]
    public void UnaryMinus_BindsLooserThanPower()
    {
        // -2^2 must be -(2^2) = -4, matching Python's -2**2, not (-2)^2 = 4
        Assert.Equal(-4, Eval("-2^2"));
    }

    [Fact]
    public void UnaryMinus_OnPowerRightHandSide()
    {
        Assert.Equal(0.25, Eval("2^-2"));
    }

    [Fact]
    public void NestedExpression_AsPowerBase()
    {
        // (a+b)^2 - the base of ^ must accept an arbitrary sub-expression
        Assert.Equal(25, Eval("(a+b)^2", a: 2, b: 3));
    }

    [Theory]
    [InlineData(3, 4, 5)]
    [InlineData(6, 8, 10)]
    public void Sqrt_OfSumOfSquares(double c, double d, double expected)
    {
        Assert.Equal(expected, Eval("sqrt(c^2 + d^2)", c: c, d: d), precision: 9);
    }

    [Fact]
    public void Log_MatchesMathLog()
    {
        Assert.Equal(1.0, Eval("log(b) + c", b: Math.E, c: 0), precision: 9);
    }

    [Fact]
    public void Abs_OfDifference()
    {
        Assert.Equal(7, Eval("abs(d - b)", b: 10, d: 3));
    }

    [Fact]
    public void Condition_TrueBranch_EvaluatesGreaterThan()
    {
        // if(a > 5, b*2, b/2) with a=10 -> true branch (b*2)
        var tnai = FormulaParser.Parse("a > 5");
        Assert.Equal(1.0, tnai.Eval(a: 10, b: 0, c: 0, d: 0));
        Assert.Equal(16.0, Eval("b * 2", b: 8));
    }

    [Fact]
    public void Condition_FalseBranch_EvaluatesLessOrEqual()
    {
        var tnai = FormulaParser.Parse("a > 5");
        Assert.Equal(0.0, tnai.Eval(a: 2, b: 0, c: 0, d: 0));
        Assert.Equal(4.0, Eval("b / 2", b: 8));
    }

    [Fact]
    public void Equality_UsesFloatingPointTolerance()
    {
        // BinaryNode.Eval for "==" uses Math.Abs(l-r) < 1e-9, not exact
        // bitwise equality - this is intentional (see comment in
        // Formula.cs) since a and c are independently rounded random
        // floats and must still compare equal after the round-trip through
        // seed_data.py's `c := a` branch.
        Assert.Equal(1.0, Eval("a == c", a: 1.0, c: 1.0 + 1e-12));
        Assert.Equal(0.0, Eval("a == c", a: 1.0, c: 1.0001));
    }

    [Fact]
    public void InvalidSyntax_TrailingOperator_ThrowsFormatException()
    {
        Assert.Throws<FormatException>(() => FormulaParser.Parse("a + "));
    }

    [Fact]
    public void InvalidSyntax_UnmatchedParenthesis_ThrowsFormatException()
    {
        Assert.Throws<FormatException>(() => FormulaParser.Parse("(a + b"));
    }

    [Fact]
    public void InvalidSyntax_UnknownCharacter_ThrowsFormatException()
    {
        Assert.Throws<FormatException>(() => FormulaParser.Parse("a & b"));
    }

    [Fact]
    public void DisallowedVariable_ThrowsAtEvaluationTime()
    {
        // Unlike the SQL translator (which only fails once the generated
        // SQL is executed against the real table), VariableNode.Eval
        // rejects anything outside a/b/c/d directly - this is a genuine
        // behavioral difference between the two custom parsers.
        var node = FormulaParser.Parse("e + a");
        Assert.Throws<InvalidOperationException>(() => node.Eval(a: 1, b: 0, c: 0, d: 0));
    }

    [Fact]
    public void DivisionByZero_ReturnsInfinity_DoesNotThrow()
    {
        // C# double division follows IEEE 754: x/0 is +/-Infinity (or NaN
        // for 0/0), never an exception. This differs from both Python
        // (ZeroDivisionError) and SQLite (NULL) - see
        // test_formula_translator.py's equivalent test for the SQL side.
        // None of the 12 seeded formulas can hit this in practice (d/4
        // uses a constant, non-zero divisor).
        double result = Eval("a / d", a: 1, d: 0);
        Assert.True(double.IsPositiveInfinity(result));
    }

    [Fact]
    public void ZeroDividedByZero_IsNaN()
    {
        double result = Eval("a / d", a: 0, d: 0);
        Assert.True(double.IsNaN(result));
    }
}
