# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from natural.ir.models import (
    CompressStatement,
    ExamineStatement,
    ResetStatement,
    SeparateStatement,
)
from natural.normalizer.parsers.expression_parser import ExpressionParser


class StringOpParser:
    def __init__(self):
        self.expr_parser = ExpressionParser()
        self.compress_pattern = re.compile(
            r"^\s*COMPRESS\s+(.+?)\s+INTO\s+([*#\+A-Za-z0-9\-_\.]+)(?:\s+(WITH\s+ALL\s+DELIMITERS?|WITH\s+DELIMITERS?)\s+(.+?))?\s*$",
            re.IGNORECASE,
        )
        self.examine_replace = re.compile(
            r"^\s*EXAMINE\s+(.+?)\s+FOR\s+(.+?)\s+REPLACE\s+(?:FIRST\s+)?WITH\s+(.+?)\s*$",
            re.IGNORECASE,
        )
        self.examine_count = re.compile(
            r"^\s*EXAMINE\s+(.+?)\s+FOR\s+(.+?)\s+GIVING\s+NUMBER\s+(?:IN\s+)?(.+?)\s*$",
            re.IGNORECASE,
        )
        self.examine_translate = re.compile(
            r"^\s*EXAMINE\s+(?:FULL\s+)?(?:VALUE\s+OF\s+)?(.+?)\s+TRANSLATE\s+INTO\s+(UPPER|LOWER)(?:\s+CASE)?\s*$",
            re.IGNORECASE,
        )
        self.separate_pattern = re.compile(
            r"^\s*SEPARATE\s+(.+?)\s+INTO\s+(.+?)(?:\s+WITH\s+DELIMITERS?\s+(.+?))?(?:\s+(IGNORE\s+REMAINDER))?\s*$",
            re.IGNORECASE,
        )
        self.reset_pattern = re.compile(
            r"^\s*RESET\s+(INITIAL\s+)?(.+)$",
            re.IGNORECASE,
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

        return CompressStatement(
            operands=operands,
            target=target,
            delimiter=delim,
            with_delimiters=bool(delim_clause),
        )

    def parse_separate(self, raw_statement: str) -> SeparateStatement:
        clean = re.sub(r"/\*.*$", "", raw_statement).strip()
        m = self.separate_pattern.match(clean)
        if not m:
            raise ValueError(f"Invalid SEPARATE syntax: {raw_statement}")

        source_raw = m.group(1).strip()
        targets_raw = m.group(2).strip().split()
        delim_raw = m.group(3)
        ignore_remainder = bool(m.group(4))

        source = self.expr_parser.parse(source_raw)
        targets = [self.expr_parser.parse(t) for t in targets_raw if t.strip()]
        delim = self.expr_parser.parse(delim_raw.strip()) if delim_raw else None

        return SeparateStatement(
            source=source,
            targets=targets,
            delimiter=delim,
            ignore_remainder=ignore_remainder,
        )

    def parse_examine(self, raw_statement: str) -> ExamineStatement:
        clean = re.sub(r"/\*.*$", "", raw_statement).strip()

        m_trans = self.examine_translate.match(clean)
        if m_trans:
            target = self.expr_parser.parse(m_trans.group(1).strip())
            case_type = m_trans.group(2).upper()
            return ExamineStatement(target=target, translate_case=case_type)

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
