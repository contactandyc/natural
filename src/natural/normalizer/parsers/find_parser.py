import re
from lark import Lark, Transformer
from natural.ir.models import FindStatement, Expression

find_grammar = r"""
    ?start: find_clause
    
    // e.g. "(1) EMP-VIEW WITH NAME = #INPUT-ID"
    find_clause: [limit] view_name "WITH" descriptor "=" operand
    
    limit: "(" NUMBER ")"
    view_name: /[A-Z0-9\-\_]+/
    descriptor: /[A-Z0-9\-\_]+/
    operand: /[A-Z0-9\-\_\#]+/ | NUMBER | STRING
    
    NUMBER: /\d+/
    STRING: /'[^']*'/
    
    %import common.WS
    %ignore WS
"""

class FindTransformer(Transformer):
    def limit(self, tokens):
        return int(tokens[0])

    def view_name(self, tokens):
        return str(tokens[0])

    def descriptor(self, tokens):
        return str(tokens[0])

    def operand(self, tokens):
        val = str(tokens[0])
        kind = "literal" if val.isdigit() or val.startswith("'") else "ref"
        return Expression(kind=kind, value=val.strip("'"))

    def find_clause(self, children):
        # If limit is present, it's children[0], else handle offset
        has_limit = isinstance(children[0], int)
        idx = 1 if has_limit else 0

        return FindStatement(
            view_name=children[idx],
            descriptor=children[idx+1],
            operand=children[idx+2],
            body=[],      # Filled later by the dispatcher
            on_empty=[]   # Filled later by the dispatcher
        )

class FindParser:
    def __init__(self):
        self.parser = Lark(find_grammar, parser="lalr")
        self.transformer = FindTransformer()

    def parse(self, raw_clause: str) -> FindStatement:
        clean_clause = re.sub(r"/\*.*$", "", raw_clause).strip()
        tree = self.parser.parse(clean_clause)
        return self.transformer.transform(tree)
