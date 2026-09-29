# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from pathlib import Path
from lark import Lark, Transformer, Token
from natural.normalizer.workspace import Workspace
from natural.normalizer.preprocessor import NaturalPreprocessor
from natural.ir.pass1_models import (
    Pass1Module,
    RawStatement,
    DefineDataBlock,
    FindBlock,
    IfBlock,
    RepeatBlock,
    ForBlock,
    ReadBlock,
    HistogramBlock,
    ReadWorkBlock,
    DecideBlock,
    DecideBranchBlock,
    NoneBranchBlock,
    SubroutineBlock,
    FunctionBlock,
    OnErrorBlock,
    AtStartBlock,
    AtEndBlock,
    AtBreakBlock,
    BeforeBreakBlock,
)


class IslandTransformer(Transformer):
    def label(self, tokens) -> str:
        return str(tokens[0]).rstrip(".").strip()

    def raw_clause(self, tokens) -> str:
        return str(tokens[0]).strip()

    def raw_statement(self, tokens) -> RawStatement:
        return RawStatement(text=str(tokens[0]).strip())

    def define_data_block(self, tokens) -> DefineDataBlock:
        content = str(tokens[0]).strip() if len(tokens) > 0 and tokens[0] is not None else ""
        return DefineDataBlock(raw_content=content)

    def _extract_label_and_clause(self, children):
        filtered = [c for c in children if c is not None]
        if not filtered:
            return None, "", []

        non_body_types = (
            Pass1Module,
            RawStatement,
            FindBlock,
            ReadBlock,
            HistogramBlock,
            RepeatBlock,
            ForBlock,
            IfBlock,
            DecideBlock,
            ReadWorkBlock,
            OnErrorBlock,
            AtStartBlock,
            AtEndBlock,
            AtBreakBlock,
            BeforeBreakBlock,
            FunctionBlock,
        )
        if len(filtered) > 1 and isinstance(filtered[0], str) and not isinstance(filtered[1], non_body_types):
            label = str(filtered[0])
            clause = str(filtered[1])
            body = filtered[2:]
        else:
            label = None
            clause = str(filtered[0])
            body = filtered[1:]

        return label, clause, body

    def find_block(self, children) -> FindBlock:
        label, clause, body = self._extract_label_and_clause(children)
        return FindBlock(label=label, raw_clause=clause, body=body)

    def read_block(self, children) -> ReadBlock:
        label, clause, body = self._extract_label_and_clause(children)
        return ReadBlock(label=label, raw_clause=clause, body=body)

    def histogram_block(self, children) -> HistogramBlock:
        label, clause, body = self._extract_label_and_clause(children)
        return HistogramBlock(label=label, raw_clause=clause, body=body)

    def read_work_block(self, children) -> ReadWorkBlock:
        label, clause, body = self._extract_label_and_clause(children)
        return ReadWorkBlock(label=label, raw_clause=clause, body=body)

    def on_error_block(self, children) -> OnErrorBlock:
        body = [c for c in children if c is not None]
        return OnErrorBlock(body=body)

    def at_start_block(self, children) -> AtStartBlock:
        body = [c for c in children if c is not None]
        return AtStartBlock(body=body)

    def at_end_block(self, children) -> AtEndBlock:
        body = [c for c in children if c is not None]
        return AtEndBlock(body=body)

    def at_break_block(self, children) -> AtBreakBlock:
        label, clause, body = self._extract_label_and_clause(children)
        return AtBreakBlock(label=label, raw_clause=clause, body=body)

    def before_break_block(self, children) -> BeforeBreakBlock:
        body = [c for c in children if c is not None]
        return BeforeBreakBlock(body=body)

    def if_block(self, children) -> IfBlock:
        filtered = [c for c in children if c is not None]
        clause = str(filtered[0])
        body = []
        else_body = []
        target = body

        for c in filtered[1:]:
            if isinstance(c, Token) and c.type == "ELSE":
                target = else_body
            else:
                target.append(c)

        return IfBlock(raw_clause=clause, body=body, else_body=else_body)

    def repeat_block(self, children) -> RepeatBlock:
        filtered = [c for c in children if c is not None]
        label = None
        clause = ""
        body = []
        is_bottom = False

        non_body_types = (
            RawStatement,
            FindBlock,
            ReadBlock,
            HistogramBlock,
            RepeatBlock,
            ForBlock,
            IfBlock,
            DecideBlock,
            ReadWorkBlock,
            OnErrorBlock,
            AtStartBlock,
            AtEndBlock,
            AtBreakBlock,
            BeforeBreakBlock,
            FunctionBlock,
        )
        for idx, item in enumerate(filtered):
            if isinstance(item, str) and not isinstance(item, non_body_types):
                cleaned = item.strip()
                if cleaned:
                    if idx > 0 and len(body) > 0:
                        is_bottom = True
                    clause = f"UNTIL {cleaned}" if not cleaned.upper().startswith(("UNTIL", "WHILE")) else cleaned
            else:
                body.append(item)

        return RepeatBlock(label=label, raw_clause=clause, body=body, is_post_test=is_bottom)

    def for_block(self, children) -> ForBlock:
        label, clause, body = self._extract_label_and_clause(children)
        return ForBlock(label=label, raw_clause=clause, body=body)

    def decide_branch(self, children) -> DecideBranchBlock:
        filtered = [c for c in children if c is not None]
        clause = str(filtered[0])
        body = filtered[1:]
        return DecideBranchBlock(raw_clause=clause, body=body)

    def none_branch(self, children) -> NoneBranchBlock:
        body = [c for c in children if c is not None and not isinstance(c, (Token, str))]
        return NoneBranchBlock(raw_clause="", body=body)

    def decide_on_block(self, children) -> DecideBlock:
        filtered = [c for c in children if c is not None]
        clause = str(filtered[0])
        branches = [c for c in filtered[1:] if isinstance(c, DecideBranchBlock)]
        none_branch = next((c for c in filtered[1:] if isinstance(c, NoneBranchBlock)), None)
        return DecideBlock(decide_type="ON", raw_clause=clause, branches=branches, none_branch=none_branch)

    def decide_for_block(self, children) -> DecideBlock:
        filtered = [c for c in children if c is not None]
        branches = [c for c in filtered if isinstance(c, DecideBranchBlock)]
        none_branch = next((c for c in filtered if isinstance(c, NoneBranchBlock)), None)
        return DecideBlock(decide_type="FOR", raw_clause="", branches=branches, none_branch=none_branch)

    def subroutine_block(self, children) -> SubroutineBlock:
        filtered = [c for c in children if c is not None]
        name = str(filtered[0]).strip().upper()
        body = filtered[1:]
        return SubroutineBlock(name=name, body=body)

    def function_block(self, children) -> FunctionBlock:
        filtered = [c for c in children if c is not None]
        name = str(filtered[0]).strip().upper()
        returns_clause = None
        body_start = 1
        if len(filtered) > 1:
            cand = filtered[1]
            cand_text = cand.text if isinstance(cand, RawStatement) else str(cand)
            if "RETURNS" in cand_text.upper():
                returns_clause = cand_text.strip()
                body_start = 2
        body = filtered[body_start:]
        return FunctionBlock(name=name, returns_clause=returns_clause, body=body)

    def module(self, children) -> list:
        return [c for c in children if c is not None]


class Pass1Parser:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.preprocessor = NaturalPreprocessor(workspace)

        grammar_path = Path(__file__).parent.parent / "grammar" / "pass1_island.lark"
        self._lark = Lark(grammar_path.read_text(encoding="utf-8"), parser="lalr")

    def parse(self, source_code: str, module_name: str) -> Pass1Module:
        expanded_code = self.preprocessor.expand(source_code, module_name)
        tree = self._lark.parse(expanded_code)
        statements = IslandTransformer().transform(tree)
        return Pass1Module(module_name=module_name, statements=statements)

    def parse_file(self, file_path: Path | str) -> Pass1Module:
        path = Path(file_path)
        content = path.read_text(encoding="utf-8", errors="replace")
        return self.parse(content, module_name=path.stem)
