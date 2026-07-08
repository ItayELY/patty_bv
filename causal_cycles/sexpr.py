"""Minimal, dependency-free S-expression reader for PDDL.

PDDL domain/problem files are just Lisp-style S-expressions, so we don't
need the full ANTLR grammar in src/pddl to pull out ``:functions`` and
``:effect`` blocks - a small tokenizer plus a recursive-descent reader is
enough and keeps this tool independent of the rest of the codebase.

A parsed expression is either:
  * a ``str`` (a symbol, parameter, or number token), or
  * a ``list`` of expressions (a parenthesized form).
"""
from __future__ import annotations

import re
from typing import List, Union

SExpr = Union[str, List["SExpr"]]

_TOKEN_RE = re.compile(r"\(|\)|[^\s()]+")


def strip_comments(text: str) -> str:
    out = []
    for line in text.splitlines():
        idx = line.find(";")
        out.append(line if idx == -1 else line[:idx])
    return "\n".join(out)


def tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(strip_comments(text))


def parse_all(text: str) -> List[SExpr]:
    """Parse every top-level form in ``text`` (case is preserved)."""
    tokens = tokenize(text)
    pos = 0
    forms: List[SExpr] = []

    def read() -> SExpr:
        nonlocal pos
        tok = tokens[pos]
        if tok == "(":
            pos += 1
            items: List[SExpr] = []
            while tokens[pos] != ")":
                items.append(read())
            pos += 1  # consume ")"
            return items
        if tok == ")":
            raise SyntaxError("Unexpected ')' in PDDL source")
        pos += 1
        return tok

    while pos < len(tokens):
        forms.append(read())

    return forms


def head(expr: SExpr) -> str:
    """Return the lowercase leading symbol of a list expression, or ''."""
    if isinstance(expr, list) and expr and isinstance(expr[0], str):
        return expr[0].lower()
    return ""
