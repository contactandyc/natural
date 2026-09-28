# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from decimal import Decimal
from lark import Lark, Transformer
from natural.ir.models import Expression

expr_grammar = r"""
    ?start: logical_or

    ?logical_or: logical_and
               | logical_or LOGICAL_OR logical_and   -> binary_expr

    ?logical_and: comparison
                | logical_and LOGICAL_AND comparison -> binary_expr

    ?comparison: expr
               | comparison COMP_OP expr             -> binary_expr

    ?expr: term
         | expr ADD_OP term                          -> binary_expr

    ?term: factor
         | term MULT_OP factor                       -> binary_expr

    ?factor: NUMBER                                  -> num_lit
           | STRING                                  -> str_lit
           | DATE_LITERAL                            -> date_lit
           | BOOLEAN_LITERAL                         -> bool_lit
           | SYSTEM_VAR                              -> sys_var
           | VAR_NAME array_dim?                     -> var_ref
           | "(" logical_or ")"

    array_dim: "(" /[^)]+/ ")"

    LOGICAL_OR.2: "OR"i
    LOGICAL_AND.2: "AND"i
    BOOLEAN_LITERAL.3: "TRUE"i | "FALSE"i
    COMP_OP: ">=" | "<=" | "<>" | ">" | "<" | "="
    ADD_OP: "+" | "-"
    MULT_OP: "*" | "/"

    NUMBER.2: /-?\d+(\.\d+)?/
    STRING: /'[^']*'/ | /"[^"]*"/
    DATE_LITERAL: /D'[^']+'/
    SYSTEM_VAR: /\*[A-Z0-9\-_]+(?:\([A-Za-z0-9\-_.]+\))?/
    VAR_NAME: /[*#\+][A-Za-z0-9\-_]+((\.|\/)[A-Za-z0-9\-_]+)*/ | /[A-Za-z0-9\-_]+(\.|\/)[A-Za-z0-9\-_]+/ | /[A-Za-z][A-Za-z0-9\-_]*/

    %import common.WS
    %ignore WS
"""


class ExpressionTransformer(Transformer):
    def num_lit(self, tokens):
        val = str(tokens[0])
        parsed_val = Decimal(val) if "." in val else int(val)
        return Expression(kind="literal", value=parsed_val)

    def str_lit(self, tokens):
        return Expression(kind="literal", value=str(tokens[0])[1:-1])

    def date_lit(self, tokens):
        return Expression(kind="literal", value=str(tokens[0])[2:-1])

    def bool_lit(self, tokens):
        return Expression(kind="literal", value=(str(tokens[0]).upper() == "TRUE"))

    def sys_var(self, tokens):
        return Expression(kind="sys_var", value=str(tokens[0]).upper())

    def var_ref(self, tokens):
        var_name = str(tokens[0])
        dim = str(tokens[1]) if len(tokens) > 1 else None
        return Expression(kind="ref", value=var_name, array_dim=dim)

    def binary_expr(self, children):
        if len(children) == 3:
            return Expression(
                kind="binary_op",
                left=children[0],
                operator=str(children[1]).upper(),
                right=children[2],
            )
        elif len(children) == 2:
            return Expression(
                kind="binary_op",
                left=children[0],
                operator="AND",
                right=children[1],
            )
        raise ValueError(f"Unexpected children for binary_expr: {children}")


class ExpressionParser:
    def __init__(self):
        self.parser = Lark(expr_grammar, parser="lalr")
        self.transformer = ExpressionTransformer()

    def parse(self, raw_expr: str) -> Expression:
        tree = self.parser.parse(raw_expr)
        return self.transformer.transform(tree)
