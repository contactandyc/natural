# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import re
from decimal import Decimal
from typing import List
from lark import Lark, Transformer
from natural.ir.models import Expression, SubstringSpec

expr_grammar = r"""
    ?start: logical_or

    ?logical_or: logical_and
               | logical_or LOGICAL_OR logical_and   -> binary_expr

    ?logical_and: comparison
                | logical_and LOGICAL_AND comparison -> binary_expr

    ?comparison: expr
               | comparison COMP_OP expr              -> binary_expr

    ?expr: term
         | expr ADD_OP term                          -> binary_expr

    ?term: power
         | term MULT_OP power                        -> binary_expr

    ?power: factor
          | power POWER_OP factor                    -> binary_expr

    ?factor: NUMBER                                  -> num_lit
           | STRING                                  -> str_lit
           | DATE_LITERAL                            -> date_lit
           | BOOLEAN_LITERAL                         -> bool_lit
           | SYSTEM_VAR                              -> sys_var
           | substring_func                          -> substring_expr
           | VAR_NAME "(" [RAW_BRACKET] ")"          -> var_with_bracket
           | VAR_NAME                                -> var_ref
           | tuple_expr
           | "(" logical_or ")"

    tuple_expr: "(" expr ("," expr)+ ")"
    substring_func: "SUBSTRING"i "(" VAR_NAME "," expr ("," expr)? ")"
    RAW_BRACKET.2: /[^)]+/

    LOGICAL_OR.2: "OR"i
    LOGICAL_AND.2: "AND"i
    BOOLEAN_LITERAL.3: "TRUE"i | "FALSE"i
    COMP_OP: ">=" | "<=" | "<>" | ">" | "<" | "="
    ADD_OP: "+" | "-"
    MULT_OP: "*" | "/" | "%" | "MOD"i
    POWER_OP.2: "**" | "^"

    NUMBER.2: /-?\d+(\.\d+)?/
    STRING: /'[^']*'/ | /"[^"]*"/
    DATE_LITERAL: /D'[^']+'/
    SYSTEM_VAR.2: /\*[A-Z0-9\-_]+(?:\([*#\+A-Za-z0-9\-_. ]+\))?/
    VAR_NAME: /[*#\+][A-Za-z0-9\-_#]+((\.|\/)[A-Za-z0-9\-_#]+)*/ | /[A-Za-z][A-Za-z0-9\-_#]*((\.|\/)[A-Za-z0-9\-_#]+)*/

    %import common.WS
    %ignore WS
"""


def _split_args(content: str) -> List[str]:
    """Splits arguments by comma while respecting nested parentheses and string quotes."""
    args = []
    current = []
    depth = 0
    in_quote = False
    quote_char = ""
    for char in content:
        if char in ("'", '"'):
            if not in_quote:
                in_quote = True
                quote_char = char
            elif quote_char == char:
                in_quote = False
        if not in_quote:
            if char in ("(", "["):
                depth += 1
            elif char in (")", "]"):
                depth -= 1
            elif char == "," and depth == 0:
                args.append("".join(current).strip())
                current = []
                continue
        current.append(char)
    if current:
        tail = "".join(current).strip()
        if tail:
            args.append(tail)
    return args


_cached_expr_parser = None


def _get_expr_parser():
    global _cached_expr_parser
    if _cached_expr_parser is None:
        _cached_expr_parser = ExpressionParser()
    return _cached_expr_parser


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
        return Expression(kind="ref", value=var_name)

    def tuple_expr(self, children):
        elements = [c for c in children if isinstance(c, Expression)]
        return Expression(kind="tuple", array_indices=elements)

    def var_with_bracket(self, tokens):
        var_name = str(tokens[0])
        raw_content = str(tokens[1]).strip() if len(tokens) > 1 and tokens[1] is not None else ""
        sub_parser = _get_expr_parser()

        if ":" in raw_content:
            parts = raw_content.split(":", 1)
            left_part = parts[0].strip()
            right_part = parts[1].strip()
            p1 = sub_parser.parse(left_part) if left_part else Expression(kind="literal", value=1)
            p2 = sub_parser.parse(right_part) if right_part else None
            return Expression(
                kind="ref",
                value=var_name,
                substring=SubstringSpec(start=p1, length=p2),
            )

        if var_name.upper().startswith(("F#", "FN#", "UDF#")):
            arg_strs = _split_args(raw_content) if raw_content else []
            args = [sub_parser.parse(a) for a in arg_strs]
            return Expression(
                kind="func_call",
                func_name=var_name,
                func_args=args,
            )

        if raw_content:
            if "," in raw_content:
                idx_strs = _split_args(raw_content)
                indices = [sub_parser.parse(a) for a in idx_strs]
            elif re.match(r"^\d+\.\d+$", raw_content):
                indices = [sub_parser.parse(p) for p in raw_content.split(".")]
            else:
                indices = [sub_parser.parse(raw_content)]
            return Expression(kind="ref", value=var_name, array_dim=raw_content, array_indices=indices)

        return Expression(kind="ref", value=var_name)

    def substring_expr(self, tokens):
        clause_tokens = tokens[0]
        var_name = str(clause_tokens[0])
        start = clause_tokens[1]
        length = clause_tokens[2] if len(clause_tokens) > 2 else None
        return Expression(
            kind="ref",
            value=var_name,
            substring=SubstringSpec(start=start, length=length),
        )

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
        self._lark = Lark(expr_grammar, parser="lalr")
        self._transformer = ExpressionTransformer()

    def parse(self, raw_expr: str) -> Expression:
        clean = raw_expr.strip()
        tree = self._lark.parse(clean)
        return self._transformer.transform(tree)
