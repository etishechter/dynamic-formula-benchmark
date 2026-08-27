"""Translates the shared formula syntax (a,b,c,d; + - * / ^; sqrt/log/abs;
comparisons) into a SQL expression string, via a small tokenizer +
recursive-descent parser (mirrors solutions/csharp_solution/Formula.cs).

A real parser (rather than a regex replace) is needed because '^' has no
SQL equivalent - it must become power(x, y) - and the operands of '^' can be
arbitrary sub-expressions (e.g. (a+b)^2, not just a single token like "c").

Precedence (low to high): comparison > +- > */ > unary minus > ^ > primary.
Unary minus binds looser than '^' on its own left (-a^2 == -(a^2), matching
Python's "-2**2 == -4"), matching solutions/csharp_solution/Formula.cs.
"""
import re
from dataclasses import dataclass
from typing import Union

_TOKEN_RE = re.compile(
    r"""
      (?P<num>\d+(?:\.\d+)?)
    | (?P<ident>[a-zA-Z]+)
    | (?P<cmp>>=|<=|==|!=|>|<)
    | (?P<op>[+\-*/^(),])
    | (?P<ws>\s+)
    """,
    re.VERBOSE,
)


@dataclass
class Num:
    value: str


@dataclass
class Var:
    name: str


@dataclass
class Unary:
    operand: "Node"


@dataclass
class Bin:
    op: str
    left: "Node"
    right: "Node"


@dataclass
class Call:
    name: str
    arg: "Node"


Node = Union[Num, Var, Unary, Bin, Call]


def _tokenize(expr: str) -> list[str]:
    tokens = []
    pos = 0
    while pos < len(expr):
        m = _TOKEN_RE.match(expr, pos)
        if not m:
            raise ValueError(f"Unexpected character {expr[pos]!r} in formula: {expr}")
        pos = m.end()
        if m.lastgroup == "ws":
            continue
        tokens.append(m.group())
    tokens.append("$END")
    return tokens


class _Parser:
    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> str:
        return self.tokens[self.pos]

    def advance(self) -> str:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def parse(self) -> Node:
        node = self.parse_comparison()
        if self.peek() != "$END":
            raise ValueError(f"Unexpected token {self.peek()!r}")
        return node

    def parse_comparison(self) -> Node:
        left = self.parse_additive()
        if self.peek() in (">", "<", ">=", "<=", "==", "!="):
            op = self.advance()
            right = self.parse_additive()
            return Bin(op, left, right)
        return left

    def parse_additive(self) -> Node:
        left = self.parse_multiplicative()
        while self.peek() in ("+", "-"):
            op = self.advance()
            right = self.parse_multiplicative()
            left = Bin(op, left, right)
        return left

    def parse_multiplicative(self) -> Node:
        left = self.parse_unary()
        while self.peek() in ("*", "/"):
            op = self.advance()
            right = self.parse_unary()
            left = Bin(op, left, right)
        return left

    def parse_unary(self) -> Node:
        if self.peek() == "-":
            self.advance()
            return Unary(self.parse_unary())
        return self.parse_power()

    def parse_power(self) -> Node:
        left = self.parse_primary()
        if self.peek() == "^":
            self.advance()
            right = self.parse_unary()  # right-associative, allows 2^-2
            return Bin("^", left, right)
        return left

    def parse_primary(self) -> Node:
        tok = self.peek()

        if re.fullmatch(r"\d+(\.\d+)?", tok):
            self.advance()
            return Num(tok)

        if re.fullmatch(r"[a-zA-Z]+", tok):
            self.advance()
            if self.peek() == "(":
                self.advance()
                arg = self.parse_comparison()
                if self.advance() != ")":
                    raise ValueError(f"Expected ')' after function '{tok}'")
                return Call(tok.lower(), arg)
            return Var(tok.lower())

        if tok == "(":
            self.advance()
            inner = self.parse_comparison()
            if self.advance() != ")":
                raise ValueError("Expected ')'")
            return inner

        raise ValueError(f"Unexpected token {tok!r}")


def parse_formula(expr: str) -> Node:
    return _Parser(_tokenize(expr)).parse()


_SQL_CMP = {"==": "=", "!=": "<>"}


def to_sql(node: Node) -> str:
    if isinstance(node, Num):
        return node.value
    if isinstance(node, Var):
        return node.name
    if isinstance(node, Unary):
        return f"(-{to_sql(node.operand)})"
    if isinstance(node, Call):
        return f"{node.name}({to_sql(node.arg)})"
    if isinstance(node, Bin):
        if node.op == "^":
            return f"power({to_sql(node.left)},{to_sql(node.right)})"
        op = _SQL_CMP.get(node.op, node.op)
        return f"({to_sql(node.left)}{op}{to_sql(node.right)})"
    raise TypeError(f"Unknown node: {node!r}")


def formula_to_sql(expr: str) -> str:
    """Parses the shared formula syntax and returns the equivalent SQL text."""
    return to_sql(parse_formula(expr))
