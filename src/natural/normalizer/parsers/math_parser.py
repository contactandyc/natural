# src/natural/normalizer/parsers/math_parser.py
# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from lark import Lark
from typing import List
from natural.ir.models import AssignStatement, Expression
from natural.normalizer.parsers.expression_parser import SHARED_EXPR_GRAMMAR, ExpressionTransformer

math_grammar = f"""
    ?start: math_stmt
    ?math_stmt: add_stmt | sub_stmt | mult_stmt | div_stmt

    add_stmt: "ADD"i rounded_flag? expr+ dest_clause
    dest_clause: "TO"i expr giving_clause? -> to_dest
               | "GIVING"i expr            -> giving_dest

    sub_stmt: "SUBTRACT"i rounded_flag? expr+ "FROM"i expr giving_clause?
    mult_stmt: "MULTIPLY"i rounded_flag? expr "BY"i expr giving_clause?
    div_stmt: "DIVIDE"i rounded_flag? expr "INTO"i expr giving_clause? remainder_clause?

    giving_clause: "GIVING"i expr
    remainder_clause: "REMAINDER"i expr
    rounded_flag: "ROUNDED"i

    {SHARED_EXPR_GRAMMAR}
"""

class MathTransformer(ExpressionTransformer):
    def rounded_flag(self, children):
        return True

    def giving_clause(self, children):
        return ("giving", children[0])

    def remainder_clause(self, children):
        return ("remainder", children[0])

    def to_dest(self, children):
        giving = next((c for c in children if isinstance(c, tuple) and c[0] == "giving"), None)
        return ("to", children[0], giving[1] if giving else None)

    def giving_dest(self, children):
        return ("giving_only", children[0])

    def add_stmt(self, children):
        is_rounded = True in children
        exprs = [c for c in children if isinstance(c, Expression)]
        dest_info = next(c for c in children if isinstance(c, tuple) and c[0] in ("to", "giving_only"))

        if dest_info[0] == "to":
            target_expr = dest_info[1]
            giving_target = dest_info[2]
            current_expr = target_expr
            for operand in exprs:
                current_expr = Expression(kind="binary_op", operator="+", left=current_expr, right=operand)
        else:
            giving_target = dest_info[1]
            current_expr = exprs[0]
            for operand in exprs[1:]:
                current_expr = Expression(kind="binary_op", operator="+", left=current_expr, right=operand)

        out_target = giving_target if giving_target else target_expr if dest_info[0] == "to" else giving_target
        return [AssignStatement(target=out_target, value=current_expr, rounded=is_rounded)]

    def sub_stmt(self, children):
        is_rounded = True in children
        exprs = [c for c in children if isinstance(c, Expression)]
        target_expr = exprs[-1]
        operands = exprs[:-1]
        giving = next((c[1] for c in children if isinstance(c, tuple) and c[0] == "giving"), None)

        current_expr = target_expr
        for operand in operands:
            current_expr = Expression(kind="binary_op", operator="-", left=current_expr, right=operand)

        out_target = giving if giving else target_expr
        return [AssignStatement(target=out_target, value=current_expr, rounded=is_rounded)]

    def mult_stmt(self, children):
        is_rounded = True in children
        exprs = [c for c in children if isinstance(c, Expression)]
        val1 = exprs[0]
        val2 = exprs[1]
        giving = next((c[1] for c in children if isinstance(c, tuple) and c[0] == "giving"), None)

        binary_expr = Expression(kind="binary_op", operator="*", left=val1, right=val2)
        out_target = giving if giving else val1
        return [AssignStatement(target=out_target, value=binary_expr, rounded=is_rounded)]

    def div_stmt(self, children):
        is_rounded = True in children
        exprs = [c for c in children if isinstance(c, Expression)]
        val_expr = exprs[0]
        target_expr = exprs[1]
        giving = next((c[1] for c in children if isinstance(c, tuple) and c[0] == "giving"), None)
        remainder = next((c[1] for c in children if isinstance(c, tuple) and c[0] == "remainder"), None)

        quot_target = giving if giving else target_expr
        binary_expr = Expression(kind="binary_op", operator="/", left=target_expr, right=val_expr)
        quot_stmt = AssignStatement(target=quot_target, value=binary_expr, rounded=is_rounded)

        if remainder:
            rem_expr = Expression(kind="binary_op", operator="%", left=target_expr, right=val_expr)
            rem_stmt = AssignStatement(target=remainder, value=rem_expr, rounded=False)
            # Guarantee remainder happens first in codegen
            return [rem_stmt, quot_stmt]

        return [quot_stmt]

class MathParser:
    def __init__(self):
        self.parser = Lark(math_grammar, parser="lalr")
        self.transformer = MathTransformer()

    def parse(self, raw_statement: str) -> List[AssignStatement]:
        clean_statement = re.sub(r"/\*.*$", "", raw_statement).strip()
        tree = self.parser.parse(clean_statement)
        return self.transformer.transform(tree)
