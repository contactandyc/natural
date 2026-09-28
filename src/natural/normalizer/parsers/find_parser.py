# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import re
from natural.ir.models import FindStatement, Expression
from natural.normalizer.parsers.expression_parser import ExpressionParser


class FindParser:
    def __init__(self):
        self.expr_parser = ExpressionParser()
        self.pattern = re.compile(
            r"^\s*(?:\((\d+)\)\s+)?([A-Za-z0-9\-_]+)(?:\s+WITH\s+(.+))?\s*$",
            re.IGNORECASE | re.DOTALL,
            )

    def parse(self, raw_clause: str) -> FindStatement:
        clean = re.sub(r"/\*.*$", "", raw_clause).strip()
        m = self.pattern.match(clean)
        if not m:
            raise ValueError(f"Invalid FIND syntax: {raw_clause}")

        limit = int(m.group(1)) if m.group(1) else None
        view_name = m.group(2).upper()
        criteria_str = m.group(3).strip() if m.group(3) else None

        criteria_expr = None
        descriptor = None
        operand = None

        if criteria_str:
            criteria_expr = self.expr_parser.parse(criteria_str)
            if criteria_expr.kind == "binary_op" and criteria_expr.operator == "=":
                if criteria_expr.left and criteria_expr.left.kind == "ref":
                    descriptor = str(criteria_expr.left.value)
                    operand = criteria_expr.right

        return FindStatement(
            view_name=view_name,
            descriptor=descriptor or "",
            operand=operand or criteria_expr or Expression(kind="literal", value=True),
            criteria=criteria_expr,
            limit=limit,
            body=[],
            on_empty=[],
        )
