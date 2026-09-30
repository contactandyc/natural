# src/natural/normalizer/parsers/for_parser.py
# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from lark import Lark
from natural.ir.models import ForStatement, Expression
from natural.normalizer.parsers.expression_parser import SHARED_EXPR_GRAMMAR, ExpressionTransformer

for_grammar = f"""
    ?start: for_stmt
    
    for_stmt: VAR_NAME ":=" expr "TO"i expr step_clause?
    step_clause: "STEP"i expr

    {SHARED_EXPR_GRAMMAR}
"""

class ForTransformer(ExpressionTransformer):
    def step_clause(self, children):
        return ("step", children[0])

    def for_stmt(self, children):
        var_name = str(children[0])
        exprs = [c for c in children if isinstance(c, Expression)]

        start_expr = exprs[0]
        end_expr = exprs[1]

        step_tup = next((c for c in children if isinstance(c, tuple) and c[0] == "step"), None)
        step_expr = step_tup[1] if step_tup else None

        return ForStatement(
            label=None, # Label is injected by pass2_dispatcher
            variable=var_name,
            start_expr=start_expr,
            end_expr=end_expr,
            step_expr=step_expr,
            body=[]
        )

class ForParser:
    def __init__(self):
        self.parser = Lark(for_grammar, parser="lalr")
        self.transformer = ForTransformer()

    def parse(self, raw_clause: str, label: str = None) -> ForStatement:
        clean = re.sub(r"/\*.*$", "", raw_clause).strip()
        tree = self.parser.parse(clean)
        stmt = self.transformer.transform(tree)
        stmt.label = label
        return stmt
