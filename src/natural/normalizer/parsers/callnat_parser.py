# src/natural/normalizer/parsers/callnat_parser.py
# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from lark import Lark
from natural.ir.models import CallnatStatement, Expression
from natural.normalizer.parsers.expression_parser import SHARED_EXPR_GRAMMAR, ExpressionTransformer

callnat_grammar = rf"""
    ?start: callnat_stmt
    
    callnat_stmt: "CALLNAT"i STRING expr*
    
    {SHARED_EXPR_GRAMMAR}
"""

class CallnatTransformer(ExpressionTransformer):
    def callnat_stmt(self, children):
        subprogram = str(children[0])[1:-1]
        exprs = [c for c in children if isinstance(c, Expression)]
        return CallnatStatement(subprogram_name=subprogram, parameters=exprs)

class CallnatParser:
    def __init__(self):
        self.parser = Lark(callnat_grammar, parser="lalr")
        self.transformer = CallnatTransformer()

    def parse(self, raw_clause: str) -> CallnatStatement:
        clean = re.sub(r"/\*.*$", "", raw_clause).strip()
        tree = self.parser.parse(clean)
        return self.transformer.transform(tree)
