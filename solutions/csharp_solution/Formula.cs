using System;
using System.Collections.Generic;

namespace SolveCSharp;

/// <summary>
/// Minimal hand-written recursive-descent parser + AST evaluator for the
/// shared formula syntax (variables a,b,c,d; + - * / ^; sqrt/log/abs;
/// comparisons > < >= <= == !=). Parsing happens once per formula (compile
/// step); Eval() is then called once per data row - the .NET counterpart to
/// the Python "compile once, eval per row" approach, but using a
/// hand-rolled tree walker instead of a built-in interpreter/library.
/// </summary>
public abstract class Node
{
    public abstract double Eval(double a, double b, double c, double d);
}

public sealed class NumberNode(double value) : Node
{
    public override double Eval(double a, double b, double c, double d) => value;
}

public sealed class VariableNode(char name) : Node
{
    public override double Eval(double a, double b, double c, double d) => name switch
    {
        'a' => a,
        'b' => b,
        'c' => c,
        'd' => d,
        _ => throw new InvalidOperationException($"Unknown variable '{name}'"),
    };
}

public sealed class UnaryMinusNode(Node operand) : Node
{
    public override double Eval(double a, double b, double c, double d) => -operand.Eval(a, b, c, d);
}

public sealed class BinaryNode(string op, Node left, Node right) : Node
{
    public override double Eval(double a, double b, double c, double d)
    {
        double l = left.Eval(a, b, c, d);
        double r = right.Eval(a, b, c, d);
        return op switch
        {
            "+" => l + r,
            "-" => l - r,
            "*" => l * r,
            "/" => l / r,
            "^" => Math.Pow(l, r),
            ">" => l > r ? 1.0 : 0.0,
            "<" => l < r ? 1.0 : 0.0,
            ">=" => l >= r ? 1.0 : 0.0,
            "<=" => l <= r ? 1.0 : 0.0,
            "==" => Math.Abs(l - r) < 1e-9 ? 1.0 : 0.0,
            "!=" => Math.Abs(l - r) >= 1e-9 ? 1.0 : 0.0,
            _ => throw new InvalidOperationException($"Unknown operator '{op}'"),
        };
    }
}

public sealed class FunctionNode(string name, Node arg) : Node
{
    public override double Eval(double a, double b, double c, double d)
    {
        double x = arg.Eval(a, b, c, d);
        return name switch
        {
            "sqrt" => Math.Sqrt(x),
            "log" => Math.Log(x),
            "abs" => Math.Abs(x),
            _ => throw new InvalidOperationException($"Unknown function '{name}'"),
        };
    }
}

/// <summary>Tokenizes and parses a formula string into a Node tree.</summary>
public static class FormulaParser
{
    private enum TokKind { Number, Ident, Op, LParen, RParen, Comma, End }
    private record Token(TokKind Kind, string Text);

    public static Node Parse(string expr)
    {
        var tokens = Tokenize(expr);
        int pos = 0;
        var node = ParseComparison(tokens, ref pos);
        if (tokens[pos].Kind != TokKind.End)
            throw new FormatException($"Unexpected token '{tokens[pos].Text}' in expression: {expr}");
        return node;
    }

    private static List<Token> Tokenize(string expr)
    {
        var tokens = new List<Token>();
        int i = 0;
        while (i < expr.Length)
        {
            char ch = expr[i];
            if (char.IsWhiteSpace(ch)) { i++; continue; }

            if (char.IsDigit(ch) || ch == '.')
            {
                int start = i;
                while (i < expr.Length && (char.IsDigit(expr[i]) || expr[i] == '.')) i++;
                tokens.Add(new Token(TokKind.Number, expr[start..i]));
                continue;
            }

            if (char.IsLetter(ch))
            {
                int start = i;
                while (i < expr.Length && char.IsLetter(expr[i])) i++;
                tokens.Add(new Token(TokKind.Ident, expr[start..i]));
                continue;
            }

            if (ch is '>' or '<' or '=' or '!')
            {
                if (i + 1 < expr.Length && expr[i + 1] == '=')
                {
                    tokens.Add(new Token(TokKind.Op, expr.Substring(i, 2)));
                    i += 2;
                }
                else
                {
                    tokens.Add(new Token(TokKind.Op, ch.ToString()));
                    i++;
                }
                continue;
            }

            if (ch is '+' or '-' or '*' or '/' or '^')
            {
                tokens.Add(new Token(TokKind.Op, ch.ToString()));
                i++;
                continue;
            }

            if (ch == '(') { tokens.Add(new Token(TokKind.LParen, "(")); i++; continue; }
            if (ch == ')') { tokens.Add(new Token(TokKind.RParen, ")")); i++; continue; }
            if (ch == ',') { tokens.Add(new Token(TokKind.Comma, ",")); i++; continue; }

            throw new FormatException($"Unexpected character '{ch}' in expression: {expr}");
        }
        tokens.Add(new Token(TokKind.End, ""));
        return tokens;
    }

    private static Node ParseComparison(List<Token> t, ref int p)
    {
        var left = ParseAdditive(t, ref p);
        if (t[p].Kind == TokKind.Op && t[p].Text is ">" or "<" or ">=" or "<=" or "==" or "!=")
        {
            string op = t[p].Text; p++;
            var right = ParseAdditive(t, ref p);
            return new BinaryNode(op, left, right);
        }
        return left;
    }

    private static Node ParseAdditive(List<Token> t, ref int p)
    {
        var left = ParseMultiplicative(t, ref p);
        while (t[p].Kind == TokKind.Op && t[p].Text is "+" or "-")
        {
            string op = t[p].Text; p++;
            var right = ParseMultiplicative(t, ref p);
            left = new BinaryNode(op, left, right);
        }
        return left;
    }

    private static Node ParseMultiplicative(List<Token> t, ref int p)
    {
        var left = ParsePower(t, ref p);
        while (t[p].Kind == TokKind.Op && t[p].Text is "*" or "/")
        {
            string op = t[p].Text; p++;
            var right = ParsePower(t, ref p);
            left = new BinaryNode(op, left, right);
        }
        return left;
    }

    private static Node ParsePower(List<Token> t, ref int p)
    {
        var left = ParseUnary(t, ref p);
        if (t[p].Kind == TokKind.Op && t[p].Text == "^")
        {
            p++;
            var right = ParsePower(t, ref p); // right-associative
            return new BinaryNode("^", left, right);
        }
        return left;
    }

    private static Node ParseUnary(List<Token> t, ref int p)
    {
        if (t[p].Kind == TokKind.Op && t[p].Text == "-")
        {
            p++;
            return new UnaryMinusNode(ParseUnary(t, ref p));
        }
        return ParsePrimary(t, ref p);
    }

    private static Node ParsePrimary(List<Token> t, ref int p)
    {
        var tok = t[p];

        if (tok.Kind == TokKind.Number)
        {
            p++;
            return new NumberNode(double.Parse(tok.Text, System.Globalization.CultureInfo.InvariantCulture));
        }

        if (tok.Kind == TokKind.Ident)
        {
            // Function call: name(...)
            if (t[p + 1].Kind == TokKind.LParen)
            {
                string name = tok.Text.ToLowerInvariant();
                p += 2; // consume ident + '('
                var arg = ParseComparison(t, ref p);
                if (t[p].Kind != TokKind.RParen)
                    throw new FormatException($"Expected ')' after function '{name}'");
                p++;
                return new FunctionNode(name, arg);
            }
            // Single-letter variable a/b/c/d
            p++;
            return new VariableNode(char.ToLowerInvariant(tok.Text[0]));
        }

        if (tok.Kind == TokKind.LParen)
        {
            p++;
            var inner = ParseComparison(t, ref p);
            if (t[p].Kind != TokKind.RParen)
                throw new FormatException("Expected ')'");
            p++;
            return inner;
        }

        throw new FormatException($"Unexpected token '{tok.Text}'");
    }
}
