# src/natural/normalizer/parsers/loop_parser.py
# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from lark import Lark
from natural.ir.models import LoopStatement, Expression
from natural.normalizer.parsers.expression_parser import SHARED_EXPR_GRAMMAR, ExpressionTransformer

loop_grammar = rf"""
    ?start: loop_stmt
    
    loop_stmt: loop_kw expr
    
    loop_kw: "UNTIL"i -> until_kw
           | "WHILE"i -> while_kw

    {SHARED_EXPR_GRAMMAR}
"""

class LoopTransformer(ExpressionTransformer):
    def until_kw(self, children): return "UNTIL"
    def while_kw(self, children): return "WHILE"

    def loop_stmt(self, children):
        loop_type = children[0]
        expr = next(c for c in children if isinstance(c, Expression))
        return LoopStatement(loop_type=loop_type, condition=expr, body=[])

class LoopParser:
    def __init__(self):
        self.parser = Lark(loop_grammar, parser="lalr")
        self.transformer = LoopTransformer()

    def parse(self, raw_clause: str) -> LoopStatement:
        clean_clause = re.sub(r"/\*.*$", "", raw_clause).strip()
        if not clean_clause:
            return LoopStatement(loop_type="INFINITE", condition=None, body=[])
        tree = self.parser.parse(clean_clause)
        return self.transformer.transform(tree)
