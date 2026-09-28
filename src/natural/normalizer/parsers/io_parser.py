# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from lark import Lark, Transformer
from natural.ir.models import PrintStatement, WriteStatement, InputStatement, Expression
from natural.normalizer.parsers.expression_parser import ExpressionParser

io_grammar = r"""
    ?start: io_clause

    io_clause: IO_CMD io_operand*

    IO_CMD: "PRINT"i | "WRITE"i | "INPUT"i

    ?io_operand: modifier
               | str_with_repeat
               | var_ref
               | NUMBER          -> num_lit
               | STRING          -> str_lit
               | NEWLINE_SPLIT   -> newline
               | WRITE_TAB       -> write_tab

    str_with_repeat: STRING "(" NUMBER ")"
    modifier: "(" /[a-zA-Z0-9_]+=[^)]+/i ")"

    var_ref: VAR_NAME (PAREN_DIM | "(" /[^)]+/ ")")?

    PAREN_DIM: /\s*\([^)]+\)/

    VAR_NAME: /[*#\+][A-Za-z0-9\-_]+((\.|\/)[A-Za-z0-9\-_]+)*/ | /[A-Za-z0-9\-_]+(\.|\/)[A-Za-z0-9\-_]+/ | /[A-Za-z][A-Za-z0-9\-_]*/

    NEWLINE_SPLIT: "/"
    WRITE_TAB.2: /\d+T/i
    NUMBER.2: /\d+(\.\d+)?/
    STRING: /'[^']*'/ | /"[^"]*"/

    %import common.WS
    %ignore WS
"""


class IOTransformer(Transformer):
    def modifier(self, tokens):
        return None

    def str_with_repeat(self, tokens):
        base_str = str(tokens[0])[1:-1]
        count = int(tokens[1])
        return Expression(kind="literal", value=base_str * count)

    def num_lit(self, tokens):
        val = str(tokens[0])
        parsed = float(val) if "." in val else int(val)
        return Expression(kind="literal", value=parsed)

    def str_lit(self, tokens):
        return Expression(kind="literal", value=str(tokens[0])[1:-1])

    def var_ref(self, tokens):
        var_name = str(tokens[0])
        dim = str(tokens[1]).strip() if len(tokens) > 1 and tokens[1] is not None else None
        return Expression(kind="ref", value=var_name, array_dim=dim)

    def newline(self, tokens):
        return Expression(kind="literal", value="/")

    def write_tab(self, tokens):
        return Expression(kind="literal", value=str(tokens[0]).upper())

    def io_clause(self, children):
        cmd = str(children[0]).upper()
        items = [c for c in children[1:] if c is not None]

        if cmd == "PRINT":
            return PrintStatement(fields=items)
        elif cmd == "WRITE":
            return WriteStatement(items=items)
        elif cmd == "INPUT":
            return InputStatement(fields=items, modifiers=[])

        raise ValueError(f"Unknown IO command: {cmd}")


class IOParser:
    def __init__(self):
        self.parser = Lark(io_grammar, parser="lalr")
        self.transformer = IOTransformer()

    def parse(self, raw_clause: str):
        clean = re.sub(r"/\*.*$", "", raw_clause).strip()
        tree = self.parser.parse(clean)
        return self.transformer.transform(tree)
