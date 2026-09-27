# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

from lark import Lark, Transformer
from natural.ir.models import CallnatStatement, Expression

callnat_grammar = r"""
    ?start: callnat_clause
    
    callnat_clause: "CALLNAT"i subprogram_name operand*
    
    subprogram_name: STRING
    operand: /[A-Z0-9\-\_\#\.\(\)]+/ | NUMBER | STRING
    
    NUMBER: /\d+(\.\d+)?/
    STRING: /'[^']*'/ | /"[^"]*"/
    
    %import common.WS
    %ignore WS
"""

class CallnatTransformer(Transformer):
    def subprogram_name(self, tokens):
        return str(tokens[0])[1:-1] # Strip quotes

    def operand(self, tokens):
        val = str(tokens[0])
        kind = "literal" if val.isdigit() or val.startswith("'") or val.startswith('"') else "ref"
        return Expression(kind=kind, value=val.strip("'\""))

    def callnat_clause(self, children):
        return CallnatStatement(
            subprogram_name=children[0],
            parameters=children[1:]
        )

class CallnatParser:
    def __init__(self):
        self.parser = Lark(callnat_grammar, parser="lalr")
        self.transformer = CallnatTransformer()

    def parse(self, raw_clause: str) -> CallnatStatement:
        tree = self.parser.parse(raw_clause)
        return self.transformer.transform(tree)
