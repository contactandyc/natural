# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from natural.ir.models import CompressStatement, ExamineStatement, ResetStatement, Expression
from natural.normalizer.parsers.expression_parser import ExpressionParser


class StringOpParser:
    def __init__(self):
        self.expr_parser = ExpressionParser()
        self.compress_pattern = re.compile(
            r"^\s*COMPRESS\s+(.+?)\s+INTO\s+([*#\+A-Za-z0-9\-_\.]+)(?:\s+(WITH\s+ALL\s+DELIMITERS?|WITH\s+DELIMITERS?)\s+(.+?))?\s*$",
            re.IGNORECASE
        )
        self.examine_replace = re.compile(
            r"^\s*EXAMINE\s+(.+?)\s+FOR\s+(.+?)\s+REPLACE\s+(?:FIRST\s+)?WITH\s+(.+?)\s*$",
            re.IGNORECASE
        )
        self.examine_count = re.compile(
            r"^\s*EXAMINE\s+(.+?)\s+FOR\s+(.+?)\s+GIVING\s+NUMBER\s+(?:IN\s+)?(.+?)\s*$",
            re.IGNORECASE
        )
        self.reset_pattern = re.compile(
            r"^\s*RESET\s+(INITIAL\s+)?(.+)$",
            re.IGNORECASE
        )

    def parse_compress(self, raw_statement: str) -> CompressStatement:
        clean = re.sub(r"/\*.*$", "", raw_statement).strip()
        m = self.compress_pattern.match(clean)
        if not m:
            raise ValueError(f"Invalid COMPRESS syntax: {raw_statement}")

        operands_raw = m.group(1).split()
        target_raw = m.group(2).strip()
        delim_clause = m.group(3)
        delim_val_raw = m.group(4)

        operands = [self.expr_parser.parse(op) for op in operands_raw]
        target = self.expr_parser.parse(target_raw)
        delim = self.expr_parser.parse(delim_val_raw.strip()) if delim_val_raw else None
        with_all = bool(delim_clause and "ALL" in delim_clause.upper())

        return CompressStatement(
            operands=operands,
            target=target,
            delimiter=delim,
            with_delimiters=bool(delim_clause)
        )

    def parse_examine(self, raw_statement: str) -> ExamineStatement:
        clean = re.sub(r"/\*.*$", "", raw_statement).strip()
        m_rep = self.examine_replace.match(clean)
        if m_rep:
            target = self.expr_parser.parse(m_rep.group(1).strip())
            pattern = self.expr_parser.parse(m_rep.group(2).strip())
            replacement = self.expr_parser.parse(m_rep.group(3).strip())
            return ExamineStatement(target=target, pattern=pattern, replace_with=replacement)

        m_cnt = self.examine_count.match(clean)
        if m_cnt:
            target = self.expr_parser.parse(m_cnt.group(1).strip())
            pattern = self.expr_parser.parse(m_cnt.group(2).strip())
            count_var = self.expr_parser.parse(m_cnt.group(3).strip())
            return ExamineStatement(target=target, pattern=pattern, giving_number=count_var)

        raise ValueError(f"Invalid EXAMINE syntax: {raw_statement}")

    def parse_reset(self, raw_statement: str) -> ResetStatement:
        clean = re.sub(r"/\*.*$", "", raw_statement).strip()
        m = self.reset_pattern.match(clean)
        if not m:
            raise ValueError(f"Invalid RESET syntax: {raw_statement}")

        is_initial = bool(m.group(1))
        var_names = m.group(2).split()
        targets = [self.expr_parser.parse(v.strip()) for v in var_names if v.strip()]
        return ResetStatement(targets=targets, initial=is_initial)
