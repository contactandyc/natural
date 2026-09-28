# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import re
from natural.ir.pass1_models import (
    Pass1Module, FindBlock, DefineDataBlock,
    RawStatement, IfBlock, RepeatBlock, ReadBlock, DecideBlock,
    ForBlock, SubroutineBlock, ReadWorkBlock
)
from natural.ir.models import NaturalModule, PerformStatement
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

    def lower_module(self, pass1_ast: Pass1Module) -> NaturalModule:
        ir0_module = NaturalModule(name=pass1_ast.module_name)

        for statement in pass1_ast.statements:
            ir0_stmt = self.dispatch(statement)
            if ir0_stmt is not None:
                if isinstance(statement, SubroutineBlock):
                    ir0_module.subroutines[statement.name] = (
                        ir0_stmt if isinstance(ir0_stmt, list) else [ir0_stmt]
                    )
                elif isinstance(ir0_stmt, list):
                    ir0_module.data_areas.extend(ir0_stmt)
                else:
                    ir0_module.body.append(ir0_stmt)

        return ir0_module

    def dispatch(self, node):
        if isinstance(node, FindBlock):
            find_stmt = self.find_parser.parse(node.raw_clause)
            find_stmt.label = node.label
            find_stmt.body = [self.dispatch(child) for child in node.body if child is not None]
            return find_stmt

        elif isinstance(node, ReadBlock):
            read_stmt = self.read_parser.parse(node.raw_clause)
            read_stmt.label = node.label
            read_stmt.body = [self.dispatch(child) for child in node.body if child is not None]
            return read_stmt

        elif isinstance(node, ReadWorkBlock):
            work_stmt = self.work_parser.parse_read_clause(node.raw_clause, label=node.label)
            work_stmt.body = [self.dispatch(child) for child in node.body if child is not None]
            return work_stmt

        elif isinstance(node, IfBlock):
            if_stmt = self.if_parser.parse(node.raw_clause)
            if_stmt.then_branch = [self.dispatch(child) for child in node.body if child is not None]
            if_stmt.else_branch = [self.dispatch(child) for child in node.else_body if child is not None]
            return if_stmt

        elif isinstance(node, RepeatBlock):
            repeat_stmt = self.loop_parser.parse(node.raw_clause)
            repeat_stmt.label = node.label
            repeat_stmt.body = [self.dispatch(child) for child in node.body if child is not None]
            return repeat_stmt

        elif isinstance(node, ForBlock):
            for_stmt = self.for_parser.parse(node.raw_clause, label=node.label)
            for_stmt.body = [self.dispatch(child) for child in node.body if child is not None]
            return for_stmt

        elif isinstance(node, SubroutineBlock):
            return [self.dispatch(child) for child in node.body if child is not None]

        elif isinstance(node, DefineDataBlock):
            return self.data_parser.parse(node.raw_content)

        elif isinstance(node, RawStatement):
            text = node.text.strip().upper()

            if text.startswith("PERFORM "):
                sub_name = node.text.strip().split()[1].strip().upper()
                return PerformStatement(subroutine_name=sub_name)
            elif text.startswith(("UPDATE", "DELETE", "STORE", "GET ")):
                try:
                    return self.db_parser.parse(node.text)
                except ValueError:
                    pass
            elif text.startswith("WRITE WORK "):
                return self.work_parser.parse_write(node.text)
            elif text.startswith("CLOSE WORK "):
                return self.work_parser.parse_close(node.text)
            elif text.startswith("COMPRESS "):
                return self.string_parser.parse_compress(node.text)
            elif text.startswith("EXAMINE "):
                return self.string_parser.parse_examine(node.text)
            elif text.startswith("RESET "):
                return self.string_parser.parse_reset(node.text)
            elif text.startswith("MOVE "):
                return self.move_parser.parse(node.text)
            elif text.startswith("ESCAPE "):
                return self.escape_parser.parse(node.text)
            elif text.startswith(("ADD ", "SUBTRACT ", "MULTIPLY ", "DIVIDE ")):
                return self.math_parser.parse(node.text)
            elif text.startswith("CALLNAT "):
                return self.callnat_parser.parse(node.text)
            elif text.startswith(("PRINT ", "WRITE ", "INPUT ")):
                return self.io_parser.parse(node.text)
            elif text.startswith("ASSIGN ") or text.startswith("COMPUTE ") or ":=" in text or "=" in text:
                try:
                    return self.assign_parser.parse(node.text)
                except ValueError:
                    pass

        elif isinstance(node, DecideBlock):
            decide_stmt = self.decide_parser.parse(node.raw_clause, decide_type=node.decide_type)

            for branch_node in node.branches:
                branch_stmt = self.decide_parser.parse_branch(branch_node.raw_clause)
                branch_stmt.statements = [self.dispatch(child) for child in branch_node.body if child is not None]
                decide_stmt.branches.append(branch_stmt)

            if node.none_branch:
                decide_stmt.none_branch = [self.dispatch(child) for child in node.none_branch.body if child is not None]

            return decide_stmt

        return None
