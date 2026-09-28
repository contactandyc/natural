# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from natural.ir.models import WriteWorkFileStatement, CloseWorkFileStatement, ReadWorkFileStatement
from natural.normalizer.parsers.expression_parser import ExpressionParser


class WorkFileParser:
    def __init__(self):
        self.expr_parser = ExpressionParser()
        self.write_pattern = re.compile(r"^\s*WRITE\s+WORK\s+(?:FILE\s+)?(\d+)\s+(.+)$", re.IGNORECASE)
        self.close_pattern = re.compile(r"^\s*CLOSE\s+WORK\s+(?:FILE\s+)?(\d+)\s*$", re.IGNORECASE)
        self.read_pattern = re.compile(r"^\s*(?:FILE\s+)?(\d+)(?:\s+RECORD)?(?:\s+(.+))?$", re.IGNORECASE)

    def parse_write(self, raw_statement: str) -> WriteWorkFileStatement:
        clean = re.sub(r"/\*.*$", "", raw_statement).strip()
        m = self.write_pattern.match(clean)
        if not m:
            raise ValueError(f"Invalid WRITE WORK FILE syntax: {raw_statement}")

        num = int(m.group(1))
        field_parts = m.group(2).split()
        fields = [self.expr_parser.parse(f.strip()) for f in field_parts if f.strip()]
        return WriteWorkFileStatement(file_number=num, fields=fields)

    def parse_close(self, raw_statement: str) -> CloseWorkFileStatement:
        clean = re.sub(r"/\*.*$", "", raw_statement).strip()
        m = self.close_pattern.match(clean)
        if not m:
            raise ValueError(f"Invalid CLOSE WORK FILE syntax: {raw_statement}")
        return CloseWorkFileStatement(file_number=int(m.group(1)))

    def parse_read_clause(self, raw_clause: str, label: str = None) -> ReadWorkFileStatement:
        clean = re.sub(r"/\*.*$", "", raw_clause).strip()
        m = self.read_pattern.match(clean)
        if not m:
            raise ValueError(f"Invalid READ WORK FILE syntax: {raw_clause}")

        num = int(m.group(1))
        fields = []
        if m.group(2):
            field_parts = m.group(2).split()
            fields = [self.expr_parser.parse(f.strip()) for f in field_parts if f.strip()]

        return ReadWorkFileStatement(label=label, file_number=num, fields=fields, body=[])
