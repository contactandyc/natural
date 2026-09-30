# src/natural/normalizer/parsers/io_parser.py
# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from typing import Optional
from lark import Lark
from natural.ir.models import PrintStatement, WriteStatement, InputStatement, Expression
from natural.normalizer.parsers.expression_parser import SHARED_EXPR_GRAMMAR, ExpressionTransformer, ExpressionParser

io_grammar = rf"""
    ?start: io_stmt
    
    io_stmt: io_cmd io_operand*
    
    io_cmd: "PRINT"i -> print_cmd
          | "WRITE"i -> write_cmd
          | "INPUT"i -> input_cmd
    
    ?io_operand: modifier
               | str_with_repeat
               | WRITE_TAB       -> write_tab
               | NEWLINE_SPLIT   -> newline
               | expr

    str_with_repeat: STRING "(" NUMBER ")"
    modifier: "(" /[a-zA-Z0-9_]+=[^)]+/i ")"
    
    NEWLINE_SPLIT: "/"
    WRITE_TAB.5: /\d+[Tt]/
    
    {SHARED_EXPR_GRAMMAR}
"""

class IOTransformer(ExpressionTransformer):
    def __init__(self, expr_parser: Optional[ExpressionParser] = None):
        super().__init__()
        self.expr_parser = expr_parser or ExpressionParser()

    def print_cmd(self, children): return ("cmd", "PRINT")
    def write_cmd(self, children): return ("cmd", "WRITE")
    def input_cmd(self, children): return ("cmd", "INPUT")

    def modifier(self, children):
        return None

    def str_with_repeat(self, children):
        base_str = str(children[0])[1:-1]
        count = int(children[1])
        return Expression(kind="literal", value=base_str * count)

    def newline(self, children):
        return Expression(kind="newline", value="/")

    def write_tab(self, children):
        val_str = str(children[0]).strip().upper()
        col = int(val_str[:-1])
        return Expression(kind="tab", value=col)

    def io_stmt(self, children):
        cmd = next(c[1] for c in children if isinstance(c, tuple) and c[0] == "cmd")
        items = [c for c in children if c is not None and not isinstance(c, tuple)]

        if cmd == "PRINT":
            return PrintStatement(fields=items)
        elif cmd == "WRITE":
            return WriteStatement(items=items)
        elif cmd == "INPUT":
            return InputStatement(fields=items, modifiers=[])

        raise ValueError(f"Unknown IO command: {cmd}")

class IOParser:
    def __init__(self):
        self.expr_parser = ExpressionParser()
        self.parser = Lark(io_grammar, parser="lalr")
        self.transformer = IOTransformer(expr_parser=self.expr_parser)

    def parse(self, raw_clause: str):
        clean = re.sub(r"/\*.*$", "", raw_clause).strip()
        tree = self.parser.parse(clean)
        return self.transformer.transform(tree)
