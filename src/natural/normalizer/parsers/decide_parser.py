# src/natural/normalizer/parsers/decide_parser.py
# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from lark import Lark
from natural.ir.models import DecideStatement, DecideBranch, Expression
from natural.normalizer.parsers.expression_parser import SHARED_EXPR_GRAMMAR, ExpressionTransformer, ExpressionParser

decide_grammar = rf"""
    ?start: decide_stmt
    
    decide_stmt: ["FIRST"i] ["VALUE"i] ["OF"i] expr

    {SHARED_EXPR_GRAMMAR}
"""

class DecideTransformer(ExpressionTransformer):
    def decide_stmt(self, children):
        expr = next((c for c in children if isinstance(c, Expression)), None)
        return DecideStatement(decide_type="ON", operand=expr, branches=[], none_branch=[])

class DecideParser:
    def __init__(self):
        self.parser = Lark(decide_grammar, parser="lalr")
        self.transformer = DecideTransformer()
        self.expr_parser = ExpressionParser()

    def parse(self, raw_clause: str, decide_type: str = "ON") -> DecideStatement:
        clean_clause = re.sub(r"/\*.*$", "", raw_clause).strip()
        if decide_type == "FOR" or not clean_clause:
            return DecideStatement(decide_type="FOR", operand=None, branches=[], none_branch=[])
        tree = self.parser.parse(clean_clause)
        return self.transformer.transform(tree)

    def parse_branch(self, raw_clause: str) -> DecideBranch:
        clean_clause = re.sub(r"/\*.*$", "", raw_clause).strip()
        val_expr = self.expr_parser.parse(clean_clause)
        return DecideBranch(value=val_expr, statements=[])
