# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import re
from lark import Lark
from natural.ir.models import AssignStatement, Expression
from natural.normalizer.parsers.expression_parser import SHARED_EXPR_GRAMMAR, ExpressionTransformer, ExpressionParser

assign_grammar = f"""
    ?start: assign_stmt
    
    assign_stmt: assign_kw? rounded_flag? expr assign_op expr
    
    assign_kw: "ASSIGN"i | "COMPUTE"i
    rounded_flag: "ROUNDED"i
    assign_op: ":=" | "="
    
    {SHARED_EXPR_GRAMMAR}
"""

class AssignTransformer(ExpressionTransformer):
    def rounded_flag(self, children):
        return True

    def assign_stmt(self, children):
        # Extract expressions (target and value)
        exprs = [c for c in children if isinstance(c, Expression)]
        # Check if the ROUNDED flag was caught
        is_rounded = True in children

        return AssignStatement(
            target=exprs[0],
            value=exprs[1],
            rounded=is_rounded
        )

class AssignParser:
    def __init__(self):
        self.parser = Lark(assign_grammar, parser="lalr")
        self.transformer = AssignTransformer()
        self.expr_parser = ExpressionParser()

    def parse(self, raw_statement: str) -> AssignStatement:
        clean_statement = re.sub(r"/\*.*$", "", raw_statement).strip()
        tree = self.parser.parse(clean_statement)
        return self.transformer.transform(tree)
