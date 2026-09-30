# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from lark import Lark
from natural.ir.models import MoveStatement, MoveByNameStatement, Expression
from natural.normalizer.parsers.expression_parser import SHARED_EXPR_GRAMMAR, ExpressionTransformer

move_grammar = f"""
    ?start: move_stmt | move_by_name_stmt

    move_by_name_stmt: "MOVE"i "BY"i "NAME"i VAR_NAME "TO"i VAR_NAME

    move_stmt: "MOVE"i all_flag? edited_flag? expr "TO"i expr
    
    all_flag: "ALL"i
    edited_flag: "EDITED"i

    {SHARED_EXPR_GRAMMAR}
"""

class MoveTransformer(ExpressionTransformer):
    def all_flag(self, children): return ("all", True)
    def edited_flag(self, children): return ("edited", True)

    def move_by_name_stmt(self, tokens):
        # tokens[0] and tokens[1] are VAR_NAME strings
        return MoveByNameStatement(
            source=str(tokens[0]),
            target=str(tokens[1])
        )

    def move_stmt(self, children):
        is_all = any(isinstance(c, tuple) and c[0] == "all" for c in children)

        exprs = [c for c in children if isinstance(c, Expression)]
        source_expr = exprs[0]
        target_expr = exprs[1]

        # In Natural, the edit mask can be attached to either the source or the target
        final_mask = getattr(target_expr, "edit_mask", None) or getattr(source_expr, "edit_mask", None)

        return MoveStatement(
            source=source_expr,
            target=target_expr,
            edit_mask=final_mask,
            is_move_all=is_all
        )

class MoveParser:
    def __init__(self):
        self.parser = Lark(move_grammar, parser="lalr")
        self.transformer = MoveTransformer()

    def parse(self, raw_statement: str):
        clean_stmt = re.sub(r"/\*.*$", "", raw_statement).strip()
        tree = self.parser.parse(clean_stmt)
        return self.transformer.transform(tree)
