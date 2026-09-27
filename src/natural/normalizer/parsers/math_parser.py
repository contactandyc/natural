# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from natural.ir.models import AssignStatement, Expression
from natural.normalizer.parsers.expression_parser import ExpressionParser

class MathParser:
    def __init__(self):
        self.expr_parser = ExpressionParser()
        self.pattern = re.compile(
            r"^\s*(ADD|SUBTRACT|MULTIPLY|DIVIDE)\s+(?:ROUNDED\s+)?(.+?)\s+(TO|FROM|BY|INTO)\s+(.+)$",
            re.IGNORECASE
        )

    def parse(self, raw_statement: str) -> AssignStatement:
        # Strip trailing inline comments if present
        clean_statement = re.sub(r"/\*.*$", "", raw_statement).strip()
        match = self.pattern.match(clean_statement)
        if not match:
            raise ValueError(f"Invalid math syntax: {raw_statement}")

        op_word = match.group(1).upper()
        expr1_raw = re.sub(r"/\*.*$", "", match.group(2)).strip()
        expr2_raw = re.sub(r"/\*.*$", "", match.group(4)).strip()

        op_map = {
            "ADD": "+",
            "SUBTRACT": "-",
            "MULTIPLY": "*",
            "DIVIDE": "/"
        }
        operator = op_map[op_word]

        if op_word in ("ADD", "SUBTRACT", "DIVIDE"):
            val_expr = self.expr_parser.parse(expr1_raw)
            target_raw = expr2_raw
        else: # MULTIPLY target BY val
            target_raw = expr1_raw
            val_expr = self.expr_parser.parse(expr2_raw)

        target_ref = Expression(kind="ref", value=target_raw)

        binary_expr = Expression(
            kind="binary_op",
            operator=operator,
            left=target_ref,
            right=val_expr
        )

        return AssignStatement(target=target_raw, value=binary_expr)
