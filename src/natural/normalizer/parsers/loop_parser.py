# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import re
from natural.ir.models import LoopStatement
from natural.normalizer.parsers.expression_parser import ExpressionParser

class LoopParser:
    def __init__(self):
        self.expr_parser = ExpressionParser()
        self.condition_pattern = re.compile(r"^\s*(UNTIL|WHILE)\s+(.+)$", re.IGNORECASE)

    def parse(self, raw_clause: str) -> LoopStatement:
        # Strip trailing inline comments: /* ...
        clean_clause = re.sub(r"/\*.*$", "", raw_clause).strip()

        if not clean_clause:
            return LoopStatement(loop_type="INFINITE", condition=None, body=[])

        match = self.condition_pattern.match(clean_clause)
        if not match:
            raise ValueError(f"Invalid REPEAT clause syntax: {raw_clause}")

        loop_type = match.group(1).upper()
        raw_expr = re.sub(r"/\*.*$", "", match.group(2)).strip()

        parsed_cond = self.expr_parser.parse(raw_expr)

        return LoopStatement(
            loop_type=loop_type,
            condition=parsed_cond,
            body=[]
        )
