# src/natural/normalizer/parsers/find_parser.py
# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from lark import Lark
from natural.ir.models import FindStatement, Expression
from natural.normalizer.parsers.expression_parser import SHARED_EXPR_GRAMMAR, ExpressionTransformer

find_grammar = rf"""
    ?start: find_stmt
    
    find_stmt: limit_clause? VAR_NAME ["WITH"i expr]
    limit_clause: "(" NUMBER ")"

    {SHARED_EXPR_GRAMMAR}
"""

class FindTransformer(ExpressionTransformer):
    def limit_clause(self, children):
        return ("limit", int(children[0]))

    def find_stmt(self, children):
        limit = next((c[1] for c in children if isinstance(c, tuple) and c[0] == "limit"), None)
        view_name = next(str(c) for c in children if getattr(c, "type", None) == "VAR_NAME")
        criteria = next((c for c in children if isinstance(c, Expression)), None)

        descriptor = None
        operand = None
        if criteria and criteria.kind == "binary_op" and criteria.operator == "=":
            if criteria.left and criteria.left.kind == "ref":
                descriptor = str(criteria.left.value)
                operand = criteria.right

        return FindStatement(
            view_name=view_name.upper(),
            descriptor=descriptor or "",
            operand=operand or criteria or Expression(kind="literal", value=True),
            criteria=criteria,
            limit=limit,
            body=[],
            on_empty=[]
        )

class FindParser:
    def __init__(self):
        self.parser = Lark(find_grammar, parser="lalr")
        self.transformer = FindTransformer()

    def parse(self, raw_clause: str) -> FindStatement:
        clean = re.sub(r"/\*.*$", "", raw_clause).strip()
        tree = self.parser.parse(clean)
        return self.transformer.transform(tree)
