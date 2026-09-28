# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from typing import List
from natural.ir.models import AssignStatement, Expression
from natural.normalizer.parsers.expression_parser import ExpressionParser


class MathParser:
    def __init__(self):
        self.expr_parser = ExpressionParser()
        self.pattern = re.compile(
            r"^\s*(ADD|SUBTRACT|MULTIPLY|DIVIDE)(?:\s+(ROUNDED))?\s+(.+?)\s+(TO|FROM|BY|INTO)\s+(.+)$",
            re.IGNORECASE,
        )

    def parse(self, raw_statement: str) -> List[AssignStatement]:
        clean_statement = re.sub(r"/\*.*$", "", raw_statement).strip()
        match = self.pattern.match(clean_statement)
        if not match:
            raise ValueError(f"Invalid math syntax: {raw_statement}")

        op_word = match.group(1).upper()
        is_rounded = bool(match.group(2))
        expr1_raw = match.group(3).strip()
        expr2_raw = match.group(5).strip()

        op_map = {
            "ADD": "+",
            "SUBTRACT": "-",
            "MULTIPLY": "*",
            "DIVIDE": "/",
        }
        operator = op_map[op_word]

        if op_word in ("ADD", "SUBTRACT"):
            # Multi-operand support: ADD a b c TO total / SUBTRACT a b FROM total
            operands = [self.expr_parser.parse(op) for op in expr1_raw.split() if op.strip()]
            target_expr = self.expr_parser.parse(expr2_raw)

            current_expr = target_expr
            for operand in operands:
                current_expr = Expression(
                    kind="binary_op",
                    operator=operator,
                    left=current_expr,
                    right=operand,
                )
            return [AssignStatement(target=target_expr, value=current_expr, rounded=is_rounded)]

        elif op_word == "DIVIDE":
            # DIVIDE [ROUNDED] operand INTO target
            val_expr = self.expr_parser.parse(expr1_raw)
            target_expr = self.expr_parser.parse(expr2_raw)
            binary_expr = Expression(
                kind="binary_op",
                operator="/",
                left=target_expr,
                right=val_expr,
            )
            return [AssignStatement(target=target_expr, value=binary_expr, rounded=is_rounded)]

        else:
            # MULTIPLY [ROUNDED] target BY operand
            target_expr = self.expr_parser.parse(expr1_raw)
            val_expr = self.expr_parser.parse(expr2_raw)
            binary_expr = Expression(
                kind="binary_op",
                operator="*",
                left=target_expr,
                right=val_expr,
            )
            return [AssignStatement(target=target_expr, value=binary_expr, rounded=is_rounded)]
