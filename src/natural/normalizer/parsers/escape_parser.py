# src/natural/normalizer/parsers/escape_parser.py
# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from lark import Lark, Transformer
from natural.ir.models import EscapeStatement

escape_grammar = rf"""
    ?start: escape_stmt
    
    escape_stmt: "ESCAPE"i escape_target ["(" VAR_NAME ")"]
    
    escape_target: "TOP"i     -> top
                 | "BOTTOM"i  -> bottom
                 | "ROUTINE"i -> routine

    VAR_NAME: /[A-Za-z0-9\-_#]+/

    %import common.WS
    %ignore WS
"""

class EscapeTransformer(Transformer):
    def top(self, children): return "TOP"
    def bottom(self, children): return "BOTTOM"
    def routine(self, children): return "ROUTINE"

    def escape_stmt(self, children):
        target = children[0]
        loop_label = str(children[1]) if len(children) > 1 else None
        return EscapeStatement(
            target=target,
            loop_label=loop_label
        )

class EscapeParser:
    def __init__(self):
        self.parser = Lark(escape_grammar, parser="lalr")
        self.transformer = EscapeTransformer()

    def parse(self, raw_statement: str) -> EscapeStatement:
        clean = re.sub(r"/\*.*$", "", raw_statement).strip()
        tree = self.parser.parse(clean)
        return self.transformer.transform(tree)
