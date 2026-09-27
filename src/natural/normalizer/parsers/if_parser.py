# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import re
from natural.ir.models import ConditionalStatement
from natural.normalizer.parsers.expression_parser import ExpressionParser

class IfParser:
    def __init__(self):
        self.expr_parser = ExpressionParser()
        self.clean_pattern = re.compile(r"^(.*?)(?:\s+THEN)?\s*$", re.IGNORECASE)

    def parse(self, raw_clause: str) -> ConditionalStatement:
        # Strip trailing inline comments
        clean_raw = re.sub(r"/\*.*$", "", raw_clause).strip()
        match = self.clean_pattern.match(clean_raw)
        clean_expr = match.group(1) if match else clean_raw

        parsed_cond = self.expr_parser.parse(clean_expr)

        return ConditionalStatement(
            condition=parsed_cond,
            then_branch=[],
            else_branch=[]
        )
