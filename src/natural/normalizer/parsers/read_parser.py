import re
from lark import Lark, Transformer
from natural.ir.models import ReadStatement, Expression

read_grammar = r"""
    ?start: read_clause
    
    // e.g., "(1) MYVIEW BY NAME STARTING FROM 'SMITH'"
    read_clause: [limit] view_name ["BY"i descriptor] ["STARTING"i ["FROM"i] operand]
    
    limit: "(" NUMBER ")"
    view_name: /[A-Z0-9\-\_]+/
    descriptor: /[A-Z0-9\-\_]+/
    operand: /[A-Z0-9\-\_\#]+/ | NUMBER | STRING
    
    NUMBER: /\d+/
    STRING: /'[^']*'/
    
    %import common.WS
    %ignore WS
"""

class ReadTransformer(Transformer):
    def view_name(self, tokens):
        return ("view", str(tokens[0]))

    def descriptor(self, tokens):
        return ("desc", str(tokens[0]))

    def operand(self, tokens):
        val = str(tokens[0])
        kind = "literal" if val.isdigit() or val.startswith("'") else "ref"
        return Expression(kind=kind, value=val.strip("'"))

    def read_clause(self, children):
        stmt = ReadStatement(view_name="", body=[])

        for child in children:
            if isinstance(child, tuple):
                if child[0] == "view":
                    stmt.view_name = child[1]
                elif child[0] == "desc":
                    stmt.by_descriptor = child[1]
            elif isinstance(child, Expression):
                stmt.starting_from = child

        return stmt

class ReadParser:
    def __init__(self):
        self.parser = Lark(read_grammar, parser="lalr")
        self.transformer = ReadTransformer()

    def parse(self, raw_clause: str) -> ReadStatement:
        clean_clause = re.sub(r"/\*.*$", "", raw_clause).strip()
        tree = self.parser.parse(clean_clause)
        return self.transformer.transform(tree)
