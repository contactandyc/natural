# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

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

    // Handles '-' (55) -> repeats string N times
    str_with_repeat: STRING "(" NUMBER ")"

    // Captures modifiers like (AD=M, EM=YYYY)
    modifier: "(" /[a-zA-Z0-9_]+=[^)]+/i ")"

    // Links array dimensions directly to the variable name
    var_ref: VAR_NAME array_dim?

    array_dim: "(" /[^)]+/ ")"

    VAR_NAME: /[*#\+][A-Z0-9\-_]+((\.|\/)[A-Z0-9\-_]+)*/ | /[A-Z0-9\-_]+(\.|\/)[A-Z0-9\-_]+/ | /[A-Z][A-Z0-9\-_]*/

    NEWLINE_SPLIT: "/"

    WRITE_TAB.2: /\d+T/i
    NUMBER.2: /\d+(\.\d+)?/
    STRING: /'[^']*'/ | /"[^"]*"/

    %import common.WS
    %ignore WS
"""

class IOTransformer(Transformer):
    def __init__(self):
        super().__init__()
        self.expr_parser = ExpressionParser()

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
        dim = str(tokens[1]) if len(tokens) > 1 else None
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
        tree = self.parser.parse(raw_clause)
        return self.transformer.transform(tree)
