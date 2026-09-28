# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from natural.ir.models import ForStatement
from natural.normalizer.parsers.expression_parser import ExpressionParser


class ForParser:
    def __init__(self):
        self.expr_parser = ExpressionParser()
        self.for_pattern = re.compile(
            r"^\s*([*#\+A-Za-z0-9\-_]+)\s*:=\s*(.+?)\s+TO\s+(.+?)(?:\s+STEP\s+(.+?))?\s*$",
            re.IGNORECASE
        )

    def parse(self, raw_clause: str, label: str = None) -> ForStatement:
        clean = re.sub(r"/\*.*$", "", raw_clause).strip()
        m = self.for_pattern.match(clean)
        if not m:
            raise ValueError(f"Invalid FOR statement clause: {raw_clause}")

        var_name = m.group(1).strip()
        start_expr = self.expr_parser.parse(m.group(2).strip())
        end_expr = self.expr_parser.parse(m.group(3).strip())
        step_expr = self.expr_parser.parse(m.group(4).strip()) if m.group(4) else None

        return ForStatement(
            label=label,
            variable=var_name,
            start_expr=start_expr,
            end_expr=end_expr,
            step_expr=step_expr,
            body=[]
        )
