# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from lark import Lark, Transformer
from natural.ir.models import ReadStatement, HistogramStatement, Expression
from natural.normalizer.parsers.expression_parser import ExpressionParser

read_grammar = r"""
    ?start: read_clause
    
    read_clause: [limit] view_name ["BY"i descriptor] ["STARTING"i ["FROM"i] operand]
    
    limit: "(" NUMBER ")"
    view_name: /[A-Z0-9\-\_]+/
    descriptor: /[A-Z0-9\-\_]+/
    operand: /[A-Z0-9\-\_\#]+/ | NUMBER | STRING
    
    NUMBER: /\d+/
    STRING: /'[^']*'/
    
    %import common.WS
    %ignore WS
"""


class ReadTransformer(Transformer):
    def view_name(self, tokens):
        return ("view", str(tokens[0]))

    def descriptor(self, tokens):
        return ("desc", str(tokens[0]))

    def limit(self, tokens):
        return ("limit", int(tokens[0]))

    def operand(self, tokens):
        val = str(tokens[0])
        kind = "literal" if val.isdigit() or val.startswith("'") else "ref"
        return Expression(kind=kind, value=val.strip("'"))

    def read_clause(self, children):
        stmt = ReadStatement(view_name="", body=[])

        for child in children:
            if isinstance(child, tuple):
                if child[0] == "view":
                    stmt.view_name = child[1]
                elif child[0] == "desc":
                    stmt.by_descriptor = child[1]
                elif child[0] == "limit":
                    stmt.limit = child[1]
            elif isinstance(child, Expression):
                stmt.starting_from = child

        return stmt


class ReadParser:
    def __init__(self):
        self.parser = Lark(read_grammar, parser="lalr")
        self.transformer = ReadTransformer()
        self.expr_parser = ExpressionParser()
        self.histogram_pattern = re.compile(
            r"^\s*(?:\((\d+)\)\s+)?([A-Za-z0-9\-_]+)\s+FOR\s+([A-Za-z0-9\-_]+)(?:\s+STARTING\s+(?:FROM\s+)?([^\s]+))?(?:\s+THRU\s+([^\s]+))?\s*$",
            re.IGNORECASE,
        )

    def parse(self, raw_clause: str) -> ReadStatement:
        clean_clause = re.sub(r"/\*.*$", "", raw_clause).strip()
        tree = self.parser.parse(clean_clause)
        return self.transformer.transform(tree)

    def parse_histogram(self, raw_clause: str) -> HistogramStatement:
        clean = re.sub(r"/\*.*$", "", raw_clause).strip()
        m = self.histogram_pattern.match(clean)
        if not m:
            raise ValueError(f"Invalid HISTOGRAM syntax: {raw_clause}")

        limit = int(m.group(1)) if m.group(1) else None
        view_name = m.group(2).upper()
        descriptor = m.group(3).upper()
        starting_from = self.expr_parser.parse(m.group(4).strip()) if m.group(4) else None
        thru_value = self.expr_parser.parse(m.group(5).strip()) if m.group(5) else None

        return HistogramStatement(
            view_name=view_name,
            descriptor=descriptor,
            starting_from=starting_from,
            thru_value=thru_value,
            limit=limit,
            body=[],
        )
