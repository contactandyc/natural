# src/natural/normalizer/parsers/read_parser.py
# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from lark import Lark
from natural.ir.models import ReadStatement, HistogramStatement, Expression
from natural.normalizer.parsers.expression_parser import SHARED_EXPR_GRAMMAR, ExpressionTransformer

read_grammar = rf"""
    ?start: read_stmt | hist_stmt
    
    read_stmt: limit_clause? VAR_NAME by_clause? starting_clause? thru_clause?
    hist_stmt: limit_clause? VAR_NAME "FOR"i VAR_NAME starting_clause? thru_clause?
    
    limit_clause: "(" NUMBER ")"
    by_clause: "BY"i VAR_NAME
    starting_clause: "STARTING"i ["FROM"i] expr
    thru_clause: "THRU"i expr

    {SHARED_EXPR_GRAMMAR}
"""

class ReadTransformer(ExpressionTransformer):
    def limit_clause(self, children): return ("limit", int(children[0]))
    def by_clause(self, children): return ("by", str(children[0]))
    def starting_clause(self, children): return ("starting", children[0])
    def thru_clause(self, children): return ("thru", children[0])

    def read_stmt(self, children):
        limit = next((c[1] for c in children if isinstance(c, tuple) and c[0] == "limit"), None)
        view_name = next(str(c) for c in children if getattr(c, "type", None) == "VAR_NAME")

        by_desc = next((c[1] for c in children if isinstance(c, tuple) and c[0] == "by"), None)
        starting = next((c[1] for c in children if isinstance(c, tuple) and c[0] == "starting"), None)
        thru = next((c[1] for c in children if isinstance(c, tuple) and c[0] == "thru"), None)

        return ReadStatement(
            view_name=view_name.upper(),
            by_descriptor=by_desc.upper() if by_desc else None,
            starting_from=starting,
            thru_value=thru,
            limit=limit,
            body=[]
        )

    def hist_stmt(self, children):
        limit = next((c[1] for c in children if isinstance(c, tuple) and c[0] == "limit"), None)
        vars = [str(c) for c in children if getattr(c, "type", None) == "VAR_NAME"]

        starting = next((c[1] for c in children if isinstance(c, tuple) and c[0] == "starting"), None)
        thru = next((c[1] for c in children if isinstance(c, tuple) and c[0] == "thru"), None)

        return HistogramStatement(
            view_name=vars[0].upper(),
            descriptor=vars[1].upper(),
            starting_from=starting,
            thru_value=thru,
            limit=limit,
            body=[]
        )

class ReadParser:
    def __init__(self):
        self.parser = Lark(read_grammar, parser="lalr")
        self.transformer = ReadTransformer()

    def parse(self, raw_clause: str) -> ReadStatement:
        clean = re.sub(r"/\*.*$", "", raw_clause).strip()
        tree = self.parser.parse(clean)
        return self.transformer.transform(tree)

    def parse_histogram(self, raw_clause: str) -> HistogramStatement:
        clean = re.sub(r"/\*.*$", "", raw_clause).strip()
        tree = self.parser.parse(clean)
        return self.transformer.transform(tree)
