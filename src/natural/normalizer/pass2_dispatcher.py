# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import re
from typing import Any, List, Optional, Union

from natural.ir.pass1_models import (
    Pass1Module,
    Pass1Node,
    FindBlock,
    DefineDataBlock,
    RawStatement,
    IfBlock,
    RepeatBlock,
    ReadBlock,
    HistogramBlock,
    DecideBlock,
    ForBlock,
    SubroutineBlock,
    FunctionBlock,
    ReadWorkBlock,
    OnErrorBlock,
    AtStartBlock,
    AtEndBlock,
    AtBreakBlock,
    BeforeBreakBlock,
)
from natural.ir.models import (
    NaturalModule,
    PerformStatement,
    OnErrorBlockStatement,
    AtStartOfDataStatement,
    AtEndOfDataStatement,
    AtBreakStatement,
    StopStatement,
    TerminateStatement,
    ResizeArrayStatement,
    FetchStatement,
    FunctionDefinition,
    ScopeType,
    Expression,
    Statement,
)
from natural.normalizer.parsers.find_parser import FindParser
from natural.normalizer.parsers.data_parser import DataBlockParser
from natural.normalizer.parsers.if_parser import IfParser
from natural.normalizer.parsers.loop_parser import LoopParser
from natural.normalizer.parsers.assign_parser import AssignParser
from natural.normalizer.parsers.move_parser import MoveParser
from natural.normalizer.parsers.escape_parser import EscapeParser
from natural.normalizer.parsers.read_parser import ReadParser
from natural.normalizer.parsers.math_parser import MathParser
from natural.normalizer.parsers.callnat_parser import CallnatParser
from natural.normalizer.parsers.io_parser import IOParser
from natural.normalizer.parsers.decide_parser import DecideParser
from natural.normalizer.parsers.for_parser import ForParser
from natural.normalizer.parsers.string_parser import StringOpParser
from natural.normalizer.parsers.database_parser import DatabaseOpParser
from natural.normalizer.parsers.workfile_parser import WorkFileParser


class Pass2Dispatcher:
    def __init__(self):
        self.find_parser = FindParser()
        self.data_parser = DataBlockParser()
        self.if_parser = IfParser()
        self.loop_parser = LoopParser()
        self.assign_parser = AssignParser()
        self.move_parser = MoveParser()
        self.escape_parser = EscapeParser()
        self.read_parser = ReadParser()
        self.math_parser = MathParser()
        self.callnat_parser = CallnatParser()
        self.io_parser = IOParser()
        self.decide_parser = DecideParser()
        self.for_parser = ForParser()
        self.string_parser = StringOpParser()
        self.db_parser = DatabaseOpParser()
        self.work_parser = WorkFileParser()

    def _dispatch_children(self, children_nodes: List[Any]) -> List[Statement]:
        statements: List[Statement] = []
        for child in children_nodes:
            if child is None:
                continue
            dispatched = self.dispatch(child)
            if dispatched is None:
                continue
            if isinstance(dispatched, list):
                statements.extend(dispatched)
            elif isinstance(dispatched, Statement):
                statements.append(dispatched)
        return statements

    def _dispatch_function_block(self, node: FunctionBlock) -> FunctionDefinition:
        params = []
        body_stmts = []
        for child in node.body:
            if isinstance(child, DefineDataBlock):
                areas = self.data_parser.parse(child.raw_content)
                for area in areas:
                    if area.scope == ScopeType.PARAMETER:
                        params.extend(area.inline_fields)
            else:
                dispatched = self.dispatch(child)
                if dispatched is not None:
                    if isinstance(dispatched, list):
                        body_stmts.extend(dispatched)
                    elif isinstance(dispatched, Statement):
                        body_stmts.append(dispatched)

        return FunctionDefinition(
            name=node.name,
            returns_raw=node.returns_clause,
            parameters=params,
            body=body_stmts,
        )

    def lower_module(self, pass1_ast: Pass1Module) -> NaturalModule:
        ir0_module = NaturalModule(name=pass1_ast.module_name)

        for stmt_node in pass1_ast.statements:
            if isinstance(stmt_node, DefineDataBlock):
                areas = self.data_parser.parse(stmt_node.raw_content)
                ir0_module.data_areas.extend(areas)
            elif isinstance(stmt_node, SubroutineBlock):
                ir0_module.subroutines[stmt_node.name] = self._dispatch_children(stmt_node.body)
            elif isinstance(stmt_node, FunctionBlock):
                func_def = self._dispatch_function_block(stmt_node)
                ir0_module.functions[stmt_node.name] = func_def
            else:
                dispatched = self.dispatch(stmt_node)
                if dispatched is None:
                    continue
                if isinstance(dispatched, list):
                    ir0_module.body.extend(dispatched)
                elif isinstance(dispatched, Statement):
                    ir0_module.body.append(dispatched)

        return ir0_module

    def dispatch(self, node: Pass1Node) -> Optional[Union[Statement, List[Statement]]]:
        if isinstance(node, FindBlock):
            stmt = self.find_parser.parse(node.raw_clause)
            stmt.label = node.label
            stmt.body = self._dispatch_children(node.body)
            return stmt

        if isinstance(node, ReadBlock):
            stmt = self.read_parser.parse(node.raw_clause)
            stmt.label = node.label
            stmt.body = self._dispatch_children(node.body)
            return stmt

        if isinstance(node, HistogramBlock):
            stmt = self.read_parser.parse_histogram(node.raw_clause)
            stmt.label = node.label
            stmt.body = self._dispatch_children(node.body)
            return stmt

        if isinstance(node, ReadWorkBlock):
            stmt = self.work_parser.parse_read_clause(node.raw_clause, label=node.label)
            stmt.body = self._dispatch_children(node.body)
            return stmt

        if isinstance(node, IfBlock):
            stmt = self.if_parser.parse(node.raw_clause)
            stmt.then_branch = self._dispatch_children(node.body)
            stmt.else_branch = self._dispatch_children(node.else_body)
            return stmt

        if isinstance(node, RepeatBlock):
            stmt = self.loop_parser.parse(node.raw_clause)
            stmt.label = node.label
            stmt.body = self._dispatch_children(node.body)
            return stmt

        if isinstance(node, ForBlock):
            stmt = self.for_parser.parse(node.raw_clause, label=node.label)
            stmt.body = self._dispatch_children(node.body)
            return stmt

        if isinstance(node, OnErrorBlock):
            return OnErrorBlockStatement(body=self._dispatch_children(node.body))

        if isinstance(node, AtStartBlock):
            return AtStartOfDataStatement(body=self._dispatch_children(node.body))

        if isinstance(node, AtEndBlock):
            return AtEndOfDataStatement(body=self._dispatch_children(node.body))

        if isinstance(node, AtBreakBlock):
            field_name = node.raw_clause.strip("() ").strip() if node.raw_clause else None
            return AtBreakStatement(
                field_name=field_name,
                is_before=False,
                body=self._dispatch_children(node.body),
            )

        if isinstance(node, BeforeBreakBlock):
            return AtBreakStatement(
                field_name=None,
                is_before=True,
                body=self._dispatch_children(node.body),
            )

        if isinstance(node, DecideBlock):
            decide_stmt = self.decide_parser.parse(node.raw_clause, decide_type=node.decide_type)
            for branch_node in node.branches:
                branch = self.decide_parser.parse_branch(branch_node.raw_clause)
                branch.statements = self._dispatch_children(branch_node.body)
                decide_stmt.branches.append(branch)
            if node.none_branch:
                decide_stmt.none_branch = self._dispatch_children(node.none_branch.body)
            return decide_stmt

        if isinstance(node, RawStatement):
            return self._dispatch_raw_statement(node.text)

        return None

    def _dispatch_raw_statement(self, raw_text: str) -> Optional[Union[Statement, List[Statement]]]:
        text = raw_text.strip()
        upper = text.upper()

        if upper == "STOP" or upper.startswith("STOP "):
            return StopStatement()

        if upper == "TERMINATE" or upper.startswith("TERMINATE "):
            return TerminateStatement()

        if upper.startswith(("RESIZE ARRAY", "EXPAND ARRAY", "REDUCE ARRAY")):
            parts = text.split()
            arr_name = parts[2]
            m = re.search(r"TO\s*\((.*?)\)", text, re.IGNORECASE)
            if m:
                expr_str = m.group(1).split(":")[-1].strip()
                size_expr = self.assign_parser.expr_parser.parse(expr_str)
            else:
                size_expr = Expression(kind="literal", value=0)
            return ResizeArrayStatement(action=parts[0].upper(), array_name=arr_name, dimensions=[size_expr])

        if upper.startswith("PERFORM "):
            sub_name = text.split()[1].strip().upper()
            return PerformStatement(subroutine_name=sub_name)

        if upper.startswith("FETCH ") or upper.startswith("FETCH\t"):
            fetch_match = re.match(
                r"^\s*FETCH(?:\s+(RETURN))?\s+['\"]?([A-Za-z0-9\-_]+)['\"]?(?:\s+(.+))?\s*$",
                text,
                re.IGNORECASE,
            )
            if fetch_match:
                is_returning = bool(fetch_match.group(1))
                target_prog = fetch_match.group(2).strip().upper()
                args_raw = fetch_match.group(3).split() if fetch_match.group(3) else []
                args = [self.assign_parser.expr_parser.parse(a) for a in args_raw if a.strip()]
                return FetchStatement(
                    program_name=target_prog,
                    returning=is_returning,
                    parameters=args,
                )

        if upper.startswith(("UPDATE", "DELETE", "STORE", "GET ", "END TRANSACTION", "BACKOUT TRANSACTION")):
            try:
                return self.db_parser.parse(text)
            except ValueError:
                pass

        if upper.startswith("ACCEPT ") or upper == "ACCEPT":
            return self.db_parser.parse_accept(text)

        if upper.startswith("REJECT ") or upper == "REJECT":
            return self.db_parser.parse_reject(text)

        if upper.startswith("WRITE WORK "):
            return self.work_parser.parse_write(text)

        if upper.startswith("CLOSE WORK "):
            return self.work_parser.parse_close(text)

        if upper.startswith("COMPRESS "):
            return self.string_parser.parse_compress(text)

        if upper.startswith("SEPARATE "):
            return self.string_parser.parse_separate(text)

        if upper.startswith("EXAMINE "):
            return self.string_parser.parse_examine(text)

        if upper.startswith("RESET "):
            return self.string_parser.parse_reset(text)

        if upper.startswith("MOVE "):
            return self.move_parser.parse(text)

        if upper.startswith("ESCAPE "):
            return self.escape_parser.parse(text)

        if upper.startswith(("ADD ", "SUBTRACT ", "MULTIPLY ", "DIVIDE ")):
            return self.math_parser.parse(text)

        if upper.startswith("CALLNAT "):
            return self.callnat_parser.parse(text)

        if upper.startswith(("PRINT ", "WRITE ", "INPUT ")):
            return self.io_parser.parse(text)

        if upper.startswith(("ASSIGN ", "COMPUTE ")) or ":=" in upper or (
                "=" in upper
                and not upper.startswith(("IF ", "FIND ", "READ ", "WRITE ", "PRINT "))
                and "<=" not in upper
                and ">=" not in upper
                and "==" not in upper
        ):
            try:
                return self.assign_parser.parse(text)
            except Exception:
                pass

        return None
