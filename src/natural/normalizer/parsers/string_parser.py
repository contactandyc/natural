# src/natural/normalizer/parsers/string_parser.py
# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import re
from lark import Lark
from natural.ir.models import CompressStatement, ExamineStatement, ResetStatement, SeparateStatement, Expression
from natural.normalizer.parsers.expression_parser import SHARED_EXPR_GRAMMAR, ExpressionTransformer

string_grammar = rf"""
    ?start: string_stmt
    ?string_stmt: compress_stmt | separate_stmt | examine_stmt | reset_stmt

    compress_stmt: "COMPRESS"i ["NUMERIC"i] expr+ "INTO"i expr leaving_no_space? delim_clause? leaving_no_space?
    leaving_no_space: "LEAVING"i "NO"i ["SPACE"i]
    delim_clause: "WITH"i ["ALL"i] "DELIMITER"i ["S"i] expr

    separate_stmt: "SEPARATE"i expr "INTO"i expr+ delim_clause? ignore_remainder?
    ignore_remainder: "IGNORE"i "REMAINDER"i

    examine_stmt: "EXAMINE"i ["FULL"i] ["VALUE"i "OF"i] expr examine_action
    ?examine_action: translate_action | replace_action | count_action
    translate_action: "TRANSLATE"i "INTO"i case_type ["CASE"i]
    case_type: "UPPER"i -> upper_case
             | "LOWER"i -> lower_case
    replace_action: "FOR"i expr "REPLACE"i ["FIRST"i] "WITH"i expr
    count_action: "FOR"i expr "GIVING"i "NUMBER"i ["IN"i] expr

    reset_stmt: "RESET"i initial_flag? expr+
    initial_flag: "INITIAL"i

    {SHARED_EXPR_GRAMMAR}
"""

class StringOpTransformer(ExpressionTransformer):
    def leaving_no_space(self, children): return ("leaving_no_space", True)
    def delim_clause(self, children): return ("delim", children[0])
    def ignore_remainder(self, children): return ("ignore_remainder", True)
    def initial_flag(self, children): return ("initial", True)
    def upper_case(self, children): return "UPPER"
    def lower_case(self, children): return "LOWER"
    def translate_action(self, children): return ("translate", children[0])
    def replace_action(self, children): return ("replace", children[0], children[1])
    def count_action(self, children): return ("count", children[0], children[1])

    def compress_stmt(self, children):
        exprs = [c for c in children if isinstance(c, Expression)]
        leaving_no = any(isinstance(c, tuple) and c[0] == "leaving_no_space" for c in children)
        delim_tup = next((c for c in children if isinstance(c, tuple) and c[0] == "delim"), None)
        return CompressStatement(
            operands=exprs[:-1],
            target=exprs[-1],
            delimiter=delim_tup[1] if delim_tup else None,
            with_delimiters=bool(delim_tup),
            leaving_no_space=leaving_no
        )

    def separate_stmt(self, children):
        exprs = [c for c in children if isinstance(c, Expression)]
        delim_tup = next((c for c in children if isinstance(c, tuple) and c[0] == "delim"), None)
        ignore_rem = any(isinstance(c, tuple) and c[0] == "ignore_remainder" for c in children)
        return SeparateStatement(
            source=exprs[0],
            targets=exprs[1:],
            delimiter=delim_tup[1] if delim_tup else None,
            ignore_remainder=ignore_rem
        )

    def examine_stmt(self, children):
        exprs = [c for c in children if isinstance(c, Expression)]
        action = next(c for c in children if isinstance(c, tuple))
        if action[0] == "translate":
            return ExamineStatement(target=exprs[0], translate_case=action[1])
        elif action[0] == "replace":
            return ExamineStatement(target=exprs[0], pattern=action[1], replace_with=action[2])
        elif action[0] == "count":
            return ExamineStatement(target=exprs[0], pattern=action[1], giving_number=action[2])

    def reset_stmt(self, children):
        exprs = [c for c in children if isinstance(c, Expression)]
        initial = any(isinstance(c, tuple) and c[0] == "initial" for c in children)
        return ResetStatement(targets=exprs, initial=initial)

class StringOpParser:
    def __init__(self):
        self.parser = Lark(string_grammar, parser="lalr")
        self.transformer = StringOpTransformer()

    def parse_compress(self, raw_statement: str) -> CompressStatement: return self._parse(raw_statement)
    def parse_separate(self, raw_statement: str) -> SeparateStatement: return self._parse(raw_statement)
    def parse_examine(self, raw_statement: str) -> ExamineStatement: return self._parse(raw_statement)
    def parse_reset(self, raw_statement: str) -> ResetStatement: return self._parse(raw_statement)

    def _parse(self, raw_statement: str):
        clean = re.sub(r"/\*.*$", "", raw_statement).strip()
        tree = self.parser.parse(clean)
        return self.transformer.transform(tree)
