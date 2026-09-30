# src/natural/normalizer/parsers/if_parser.py
# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from lark import Lark
from natural.ir.models import ConditionalStatement, Expression
from natural.normalizer.parsers.expression_parser import SHARED_EXPR_GRAMMAR, ExpressionTransformer

if_grammar = rf"""
    ?start: if_stmt
    
    if_stmt: expr ["THEN"i]

    {SHARED_EXPR_GRAMMAR}
"""

class IfTransformer(ExpressionTransformer):
    def if_stmt(self, children):
        expr = next(c for c in children if isinstance(c, Expression))
        return ConditionalStatement(condition=expr, then_branch=[], else_branch=[])

class IfParser:
    def __init__(self):
        self.parser = Lark(if_grammar, parser="lalr")
        self.transformer = IfTransformer()

    def parse(self, raw_clause: str) -> ConditionalStatement:
        clean_raw = re.sub(r"/\*.*$", "", raw_clause).strip()
        tree = self.parser.parse(clean_raw)
        return self.transformer.transform(tree)
