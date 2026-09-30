# src/natural/normalizer/parsers/database_parser.py
# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from lark import Lark
from natural.ir.models import (
    UpdateStatement, GetStatement, GetSameStatement, StoreStatement,
    DeleteStatement, EndTransactionStatement, BackoutTransactionStatement,
    AcceptStatement, RejectStatement, Expression
)
from natural.normalizer.parsers.expression_parser import SHARED_EXPR_GRAMMAR, ExpressionTransformer

db_grammar = rf"""
    ?start: db_stmt
    ?db_stmt: accept_stmt | reject_stmt | get_stmt | get_same_stmt | store_stmt | update_stmt | delete_stmt | end_trans_stmt | backout_trans_stmt
    
    accept_stmt: "ACCEPT"i ["IF"i] expr
    reject_stmt: "REJECT"i ["IF"i] expr
    get_stmt: "GET"i VAR_NAME expr
    get_same_stmt: "GET"i "SAME"i VAR_NAME?
    store_stmt: "STORE"i ["RECORD"i "IN"i] VAR_NAME
    update_stmt: "UPDATE"i ["(" VAR_NAME ")"]
    delete_stmt: "DELETE"i ["(" VAR_NAME ")"]
    end_trans_stmt: "END"i "TRANSACTION"i expr?
    backout_trans_stmt: "BACKOUT"i "TRANSACTION"i
    
    {SHARED_EXPR_GRAMMAR}
"""

class DatabaseTransformer(ExpressionTransformer):
    def accept_stmt(self, children): return AcceptStatement(criteria=next(c for c in children if isinstance(c, Expression)))
    def reject_stmt(self, children): return RejectStatement(criteria=next(c for c in children if isinstance(c, Expression)))
    def get_stmt(self, children):
        return GetStatement(view_name=str(children[0]).upper(), arguments=[next(c for c in children if isinstance(c, Expression))])
    def get_same_stmt(self, children): return GetSameStatement(view_name=str(children[0]).upper() if children else None)
    def store_stmt(self, children): return StoreStatement(view_name=str(children[0]).upper())
    def update_stmt(self, children): return UpdateStatement(loop_label=str(children[0]) if children else None)
    def delete_stmt(self, children): return DeleteStatement(loop_label=str(children[0]) if children else None)
    def end_trans_stmt(self, children):
        return EndTransactionStatement(operand=next((c for c in children if isinstance(c, Expression)), None))
    def backout_trans_stmt(self, children): return BackoutTransactionStatement()

class DatabaseOpParser:
    def __init__(self):
        self.parser = Lark(db_grammar, parser="lalr")
        self.transformer = DatabaseTransformer()

    def parse_accept(self, raw_statement: str) -> AcceptStatement: return self._parse(raw_statement)
    def parse_reject(self, raw_statement: str) -> RejectStatement: return self._parse(raw_statement)
    def parse(self, raw_statement: str): return self._parse(raw_statement)

    def _parse(self, raw_statement: str):
        clean = re.sub(r"/\*.*$", "", raw_statement).strip()
        tree = self.parser.parse(clean)
        return self.transformer.transform(tree)
