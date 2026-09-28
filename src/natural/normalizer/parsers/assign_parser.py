# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import re
from natural.ir.models import AssignStatement
from natural.normalizer.parsers.expression_parser import ExpressionParser


class AssignParser:
    def __init__(self):
        self.expr_parser = ExpressionParser()
        self.assign_pattern = re.compile(
            r"^(?:ASSIGN\s+|COMPUTE\s+)?(?:\s*(ROUNDED)\s+)?(.+?)\s*(:=|=)\s*(.+)$",
            re.IGNORECASE,
        )

    def parse(self, raw_statement: str) -> AssignStatement:
        clean_statement = re.sub(r"/\*.*$", "", raw_statement).strip()
        match = self.assign_pattern.match(clean_statement)
        if not match:
            raise ValueError(f"Invalid assignment syntax: {raw_statement}")

        is_rounded = bool(match.group(1))
        target_raw = match.group(2).strip()
        raw_expr = re.sub(r"/\*.*$", "", match.group(4)).strip()

        parsed_target = self.expr_parser.parse(target_raw)
        parsed_expr = self.expr_parser.parse(raw_expr)

        return AssignStatement(target=parsed_target, value=parsed_expr, rounded=is_rounded)
