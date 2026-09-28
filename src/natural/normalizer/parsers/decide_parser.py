# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from typing import Optional
from natural.ir.models import DecideStatement, DecideBranch
from natural.normalizer.parsers.expression_parser import ExpressionParser


class DecideParser:
    def __init__(self):
        self.expr_parser = ExpressionParser()
        # Matches: [FIRST] [VALUE] [OF] #VAR
        self.decide_pattern = re.compile(r"^(?:FIRST\s+)?(?:VALUE\s+)?(?:OF\s+)?(.+)$", re.IGNORECASE)

    def parse(self, raw_clause: str, decide_type: str = "ON") -> DecideStatement:
        clean_clause = re.sub(r"/\*.*$", "", raw_clause).strip()

        if decide_type == "FOR" or not clean_clause:
            return DecideStatement(
                decide_type="FOR",
                operand=None,
                branches=[],
                none_branch=[]
            )

        match = self.decide_pattern.match(clean_clause)
        if not match:
            raise ValueError(f"Invalid DECIDE ON syntax: {raw_clause}")

        operand_raw = match.group(1).strip()
        operand_expr = self.expr_parser.parse(operand_raw)

        return DecideStatement(
            decide_type="ON",
            operand=operand_expr,
            branches=[],
            none_branch=[]
        )

    def parse_branch(self, raw_clause: str) -> DecideBranch:
        clean_clause = re.sub(r"/\*.*$", "", raw_clause).strip()
        val_expr = self.expr_parser.parse(clean_clause)
        return DecideBranch(
            value=val_expr,
            statements=[]
        )
