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
            r"^\s*(ADD|SUBTRACT|MULTIPLY|DIVIDE)(?:\s+(ROUNDED))?\s+(.+?)(?:\s+(TO|FROM|BY|INTO)\s+(.+))?$",
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
        prep = match.group(4).upper() if match.group(4) else None
        rest = match.group(5).strip() if match.group(5) else ""

        giving_target = None
        rem_target = None

        if prep:
            # Check for trailing REMAINDER
            rem_match = re.search(r"\s+REMAINDER\s+([*#\+A-Za-z0-9\-_\.]+)\s*$", rest, re.IGNORECASE)
            if rem_match:
                rem_target = self.expr_parser.parse(rem_match.group(1).strip())
                rest = rest[:rem_match.start()].strip()

            # Check for trailing GIVING
            giving_match = re.search(r"\s+GIVING\s+([*#\+A-Za-z0-9\-_\.]+)\s*$", rest, re.IGNORECASE)
            if giving_match:
                giving_target = self.expr_parser.parse(giving_match.group(1).strip())
                rest = rest[:giving_match.start()].strip()

            if not rem_target:
                rem_match = re.search(r"\s+REMAINDER\s+([*#\+A-Za-z0-9\-_\.]+)\s*$", rest, re.IGNORECASE)
                if rem_match:
                    rem_target = self.expr_parser.parse(rem_match.group(1).strip())
                    rest = rest[:rem_match.start()].strip()
        else:
            # Syntax: ADD a b GIVING c
            giving_match = re.search(r"\s+GIVING\s+([*#\+A-Za-z0-9\-_\.]+)\s*$", expr1_raw, re.IGNORECASE)
            if giving_match:
                giving_target = self.expr_parser.parse(giving_match.group(1).strip())
                expr1_raw = expr1_raw[:giving_match.start()].strip()

        if op_word == "ADD":
            operands = [self.expr_parser.parse(op) for op in expr1_raw.split() if op.strip()]
            if rest:
                target_expr = self.expr_parser.parse(rest)
                current_expr = target_expr
                for operand in operands:
                    current_expr = Expression(
                        kind="binary_op",
                        operator="+",
                        left=current_expr,
                        right=operand,
                    )
            else:
                current_expr = operands[0]
                for operand in operands[1:]:
                    current_expr = Expression(
                        kind="binary_op",
                        operator="+",
                        left=current_expr,
                        right=operand,
                    )
                target_expr = giving_target

            out_target = giving_target if giving_target else target_expr
            return [AssignStatement(target=out_target, value=current_expr, rounded=is_rounded)]

        elif op_word == "SUBTRACT":
            operands = [self.expr_parser.parse(op) for op in expr1_raw.split() if op.strip()]
            target_expr = self.expr_parser.parse(rest)
            current_expr = target_expr
            for operand in operands:
                current_expr = Expression(
                    kind="binary_op",
                    operator="-",
                    left=current_expr,
                    right=operand,
                )
            out_target = giving_target if giving_target else target_expr
            return [AssignStatement(target=out_target, value=current_expr, rounded=is_rounded)]

        elif op_word == "MULTIPLY":
            val1 = self.expr_parser.parse(expr1_raw)
            val2 = self.expr_parser.parse(rest)
            binary_expr = Expression(
                kind="binary_op",
                operator="*",
                left=val1,
                right=val2,
            )
            out_target = giving_target if giving_target else val1
            return [AssignStatement(target=out_target, value=binary_expr, rounded=is_rounded)]

        elif op_word == "DIVIDE":
            val_expr = self.expr_parser.parse(expr1_raw)
            target_expr = self.expr_parser.parse(rest)
            quot_target = giving_target if giving_target else target_expr
            binary_expr = Expression(
                kind="binary_op",
                operator="/",
                left=target_expr,
                right=val_expr,
            )
            quot_stmt = AssignStatement(target=quot_target, value=binary_expr, rounded=is_rounded)

            if rem_target:
                rem_expr = Expression(
                    kind="binary_op",
                    operator="%",
                    left=target_expr,
                    right=val_expr,
                )
                rem_stmt = AssignStatement(target=rem_target, value=rem_expr, rounded=False)
                # Remainder statement runs first to avoid operating on a mutated dividend
                return [rem_stmt, quot_stmt]

            return [quot_stmt]

        raise ValueError(f"Unknown math operation: {raw_statement}")
