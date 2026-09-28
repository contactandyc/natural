# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from typing import Optional
from natural.ir.models import UpdateStatement, GetStatement, StoreStatement, DeleteStatement
from natural.normalizer.parsers.expression_parser import ExpressionParser


class DatabaseOpParser:
    def __init__(self):
        self.expr_parser = ExpressionParser()
        self.get_pattern = re.compile(r"^\s*GET\s+([A-Z0-9\-\_]+)\s+(.+)$", re.IGNORECASE)
        self.store_pattern = re.compile(r"^\s*STORE\s+(?:RECORD\s+IN\s+)?([A-Z0-9\-\_]+)\s*$", re.IGNORECASE)
        self.delete_pattern = re.compile(r"^\s*DELETE(?:\s*\(([A-Za-z0-9\-_]+)\.?\))?\s*$", re.IGNORECASE)
        self.update_pattern = re.compile(r"^\s*UPDATE(?:\s*\(([A-Za-z0-9\-_]+)\.?\))?\s*$", re.IGNORECASE)

    def parse(self, raw_statement: str):
        clean = re.sub(r"/\*.*$", "", raw_statement).strip()

        m_upd = self.update_pattern.match(clean)
        if m_upd:
            return UpdateStatement(loop_label=m_upd.group(1))

        m_del = self.delete_pattern.match(clean)
        if m_del:
            return DeleteStatement(loop_label=m_del.group(1))

        m_store = self.store_pattern.match(clean)
        if m_store:
            return StoreStatement(view_name=m_store.group(1).upper())

        m_get = self.get_pattern.match(clean)
        if m_get:
            view_name = m_get.group(1).upper()
            args = [self.expr_parser.parse(m_get.group(2))]
            return GetStatement(view_name=view_name, arguments=args)

        raise ValueError(f"Invalid Database Op: {raw_statement}")
