# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import re
from natural.ir.models import AssignStatement
from natural.normalizer.parsers.expression_parser import ExpressionParser

class AssignParser:
    def __init__(self):
        self.expr_parser = ExpressionParser()
        self.assign_pattern = re.compile(r"^(?:ASSIGN\s+|COMPUTE\s+)?([*#\+A-Z0-9\-_\.]+)\s*(:=|=)\s*(.+)$", re.IGNORECASE)

    def parse(self, raw_statement: str) -> AssignStatement:
        # Strip trailing inline comments
        clean_statement = re.sub(r"/\*.*$", "", raw_statement).strip()
        match = self.assign_pattern.match(clean_statement)
        if not match:
            raise ValueError(f"Invalid assignment syntax: {raw_statement}")

        target = match.group(1).strip()
        raw_expr = re.sub(r"/\*.*$", "", match.group(3)).strip()

        parsed_expr = self.expr_parser.parse(raw_expr)

        return AssignStatement(target=target, value=parsed_expr)
