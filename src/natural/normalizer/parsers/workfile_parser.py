# src/natural/normalizer/parsers/workfile_parser.py
# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from lark import Lark
from natural.ir.models import WriteWorkFileStatement, CloseWorkFileStatement, ReadWorkFileStatement, Expression
from natural.normalizer.parsers.expression_parser import SHARED_EXPR_GRAMMAR, ExpressionTransformer

wf_grammar = rf"""
    ?start: wf_stmt
    ?wf_stmt: write_wf_stmt | read_wf_stmt | close_wf_stmt
    
    write_wf_stmt: "WRITE"i "WORK"i ["FILE"i] NUMBER expr+
    read_wf_stmt: ["FILE"i] NUMBER ["RECORD"i] expr*
    close_wf_stmt: "CLOSE"i "WORK"i ["FILE"i] NUMBER
    
    {SHARED_EXPR_GRAMMAR}
"""

class WorkFileTransformer(ExpressionTransformer):
    def write_wf_stmt(self, children):
        return WriteWorkFileStatement(file_number=int(children[0]), fields=[c for c in children if isinstance(c, Expression)])

    def read_wf_stmt(self, children):
        return ReadWorkFileStatement(label=None, file_number=int(children[0]), fields=[c for c in children if isinstance(c, Expression)], body=[])

    def close_wf_stmt(self, children):
        return CloseWorkFileStatement(file_number=int(children[0]))

class WorkFileParser:
    def __init__(self):
        self.parser = Lark(wf_grammar, parser="lalr")
        self.transformer = WorkFileTransformer()

    def parse_write(self, raw_statement: str) -> WriteWorkFileStatement: return self._parse(raw_statement)
    def parse_close(self, raw_statement: str) -> CloseWorkFileStatement: return self._parse(raw_statement)
    def parse_read_clause(self, raw_clause: str, label: str = None) -> ReadWorkFileStatement:
        stmt = self._parse(raw_clause)
        stmt.label = label
        return stmt

    def _parse(self, raw_statement: str):
        clean = re.sub(r"/\*.*$", "", raw_statement).strip()
        tree = self.parser.parse(clean)
        return self.transformer.transform(tree)
