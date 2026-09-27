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
    ReadBlock,
    DecideBlock,
    DecideBranchBlock,
    NoneBranchBlock,
)


class IslandTransformer(Transformer):
    def raw_clause(self, tokens) -> str:
        return str(tokens[0]).strip()

    def raw_statement(self, tokens) -> RawStatement:
        return RawStatement(text=str(tokens[0]).strip())

    def define_data_block(self, tokens) -> DefineDataBlock:
        # Since keywords are inlined/suppressed in grammar, tokens contains RAW_DATA_CONTENT if present
        content = str(tokens[0]).strip() if len(tokens) > 0 and tokens[0] is not None else ""
        return DefineDataBlock(raw_content=content)

    def find_block(self, children) -> FindBlock:
        clause = children[0]
        body = [c for c in children[1:] if c is not None]
        return FindBlock(raw_clause=clause, body=body)

    def if_block(self, children) -> IfBlock:
        clause = children[0]
        body = []
        else_body = []
        target = body

        for c in children[1:]:
            if isinstance(c, Token) and c.type == "ELSE":
                target = else_body
            elif c is not None:
                target.append(c)

        return IfBlock(raw_clause=clause, body=body, else_body=else_body)

    def repeat_block(self, children) -> RepeatBlock:
        clause = children[0]
        body = [c for c in children[1:] if c is not None]
        return RepeatBlock(raw_clause=clause, body=body)

    def read_block(self, children) -> ReadBlock:
        clause = children[0]
        body = [c for c in children[1:] if c is not None]
        return ReadBlock(raw_clause=clause, body=body)

    def decide_branch(self, children) -> DecideBranchBlock:
        clause = children[0]
        body = [c for c in children[1:] if c is not None]
        return DecideBranchBlock(raw_clause=clause, body=body)

    def none_branch(self, children) -> NoneBranchBlock:
        # Filter out literal string/token artifacts and keep AST statements
        body = [c for c in children if c is not None and not isinstance(c, (Token, str))]
        return NoneBranchBlock(raw_clause="", body=body)

    def decide_block(self, children) -> DecideBlock:
        clause = children[0]
        branches = [c for c in children[1:] if isinstance(c, DecideBranchBlock)]
        none_branch = next((c for c in children[1:] if isinstance(c, NoneBranchBlock)), None)
        return DecideBlock(raw_clause=clause, branches=branches, none_branch=none_branch)

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
