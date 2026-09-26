# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
#
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import List, Dict
from natural.ir.semantic import (
    SemanticModule,
    Symbol,
    AssignOp,
    BranchOp,
    LoopOp,
    BreakOp,
    ContinueOp,
    ReturnOp,
    QueryIterationOp,
    SemanticExpression,
)


class PythonEmitter:
    def __init__(self, module: SemanticModule):
        self.module = module
        self.indent_level = 0
        self.lines: List[str] = []
        self._sym_by_id: Dict[str, Symbol] = {s.id: s for s in module.symbols.values()}

    def _clean_name(self, name: str) -> str:
        clean = name.split(".")[-1].replace("#", "").replace("-", "_").lower()
        if clean == "class":
            return "class_"
        return clean

    def _resolve_ref(self, symbol_id: str) -> str:
        parts = symbol_id.split(".")
        if len(parts) >= 3 and parts[1] in ("local", "parameter"):
            return f"ctx.{self._clean_name(parts[-1])}"
        elif len(parts) >= 3 and parts[1] == "entity":
            return f"record.{self._clean_name(parts[-1])}"
        elif len(parts) >= 3 and parts[1] == "unresolved":
            return f"ctx.{self._clean_name(parts[-1])}_UNRESOLVED"
        return symbol_id

    def emit_line(self, line: str):
        indent = "    " * self.indent_level
        self.lines.append(f"{indent}{line}")

    def emit_expr(self, expr: SemanticExpression) -> str:
        if expr.op in ("ref", "entity_field"):
            return self._resolve_ref(expr.symbol_id)
        elif expr.op == "literal":
            return repr(expr.value)
        elif expr.op in ("multiply", "add", "subtract", "divide", "gt", "lt", "eq", "gte", "lte", "neq"):
            op_map = {
                "multiply": "*",
                "add": "+",
                "subtract": "-",
                "divide": "/",
                "gt": ">",
                "lt": "<",
                "eq": "==",
                "gte": ">=",
                "lte": "<=",
                "neq": "!=",
            }
            lhs_sym = self._sym_by_id.get(expr.lhs.symbol_id) if (expr.lhs and expr.lhs.symbol_id) else None
            if lhs_sym and lhs_sym.semantic_type.base == "date" and expr.op in ("add", "subtract"):
                lhs = self.emit_expr(expr.lhs)
                rhs_val = expr.rhs.value if expr.rhs else 1
                op = "+" if expr.op == "add" else "-"
                return f"({lhs} {op} timedelta(days={rhs_val}))"

            lhs = self.emit_expr(expr.lhs) if expr.lhs else ""
            rhs = self.emit_expr(expr.rhs) if expr.rhs else ""
            return f"({lhs} {op_map[expr.op]} {rhs})"
        return "None"

    def _convert_edit_mask(self, mask: str) -> str:
        return mask.replace("YYYY", "%Y").replace("YY", "%y").replace("MM", "%m").replace("DD", "%d")

    def emit_operation(self, op):
        if isinstance(op, AssignOp):
            target = self._resolve_ref(op.target_id)
            target_sym = self._sym_by_id.get(op.target_id)
            source_sym = self._sym_by_id.get(op.expr.symbol_id) if op.expr.symbol_id else None

            if op.edit_mask and target_sym and source_sym:
                py_mask = self._convert_edit_mask(op.edit_mask)
                if target_sym.semantic_type.base == "string" and source_sym.semantic_type.base == "date":
                    self.emit_line(f"{target} = {self._resolve_ref(op.expr.symbol_id)}.strftime('{py_mask}')")
                    return
                elif target_sym.semantic_type.base == "date" and source_sym.semantic_type.base == "string":
                    self.emit_line(f"{target} = datetime.strptime({self._resolve_ref(op.expr.symbol_id)}, '{py_mask}').date()")
                    return

            expr = self.emit_expr(op.expr)
            self.emit_line(f"{target} = {expr}")

        elif isinstance(op, BranchOp):
            cond = self.emit_expr(op.condition)
            self.emit_line(f"if {cond}:")
            self.indent_level += 1
            if not op.then_branch:
                self.emit_line("pass")
            for sub_op in op.then_branch:
                self.emit_operation(sub_op)
            self.indent_level -= 1
            if op.else_branch:
                self.emit_line("else:")
                self.indent_level += 1
                for sub_op in op.else_branch:
                    self.emit_operation(sub_op)
                self.indent_level -= 1

        elif isinstance(op, LoopOp):
            if op.loop_type == "until" and op.condition:
                cond = self.emit_expr(op.condition)
                self.emit_line(f"while not ({cond}):")
            elif op.loop_type == "while" and op.condition:
                cond = self.emit_expr(op.condition)
                self.emit_line(f"while {cond}:")
            else:
                self.emit_line("while True:")

            self.indent_level += 1
            if not op.body:
                self.emit_line("pass")
            for sub_op in op.body:
                self.emit_operation(sub_op)
            self.indent_level -= 1

        elif isinstance(op, BreakOp):
            self.emit_line("break")

        elif isinstance(op, ContinueOp):
            self.emit_line("continue")

        elif isinstance(op, ReturnOp):
            self.emit_line("return ctx")

        elif isinstance(op, QueryIterationOp):
            model_name = self._clean_name(op.entity).title().replace("_", "")
            cond = self.emit_expr(op.predicate)
            self.emit_line(f"for record in session.query({model_name}).filter({cond}):")
            self.indent_level += 1
            if not op.body:
                self.emit_line("pass")
            for sub_op in op.body:
                self.emit_operation(sub_op)
            self.indent_level -= 1

    def emit_main_block(self, class_name: str, func_name: str):
        self.emit_line("")
        self.emit_line('if __name__ == "__main__":')
        self.indent_level += 1
        self.emit_line("import sys")
        self.emit_line("import argparse")
        self.emit_line("")
        self.emit_line(f'parser = argparse.ArgumentParser(description="Standalone runner for {func_name}")')

        unique_syms = {s.id: s for s in self.module.symbols.values()}
        independent_syms = [s for s in unique_syms.values() if not s.redefine_parent]
        for sym in independent_syms:
            arg_name = f"--{self._clean_name(sym.name)}"
            self.emit_line(f'parser.add_argument("{arg_name}", type=str, default=None, help="Initial value for {arg_name}")')

        self.emit_line("args = parser.parse_args()")
        self.emit_line(f"ctx = {class_name}()")
        self.emit_line("")

        for sym in independent_syms:
            py_name = self._clean_name(sym.name)
            base_type = sym.semantic_type.base
            self.emit_line(f"if args.{py_name} is not None:")
            self.indent_level += 1
            if base_type == "date":
                self.emit_line(f"ctx.{py_name} = date.fromisoformat(args.{py_name})")
            elif base_type == "decimal":
                self.emit_line(f"ctx.{py_name} = Decimal(args.{py_name})")
            elif base_type == "integer":
                self.emit_line(f"ctx.{py_name} = int(args.{py_name})")
            elif base_type == "boolean":
                self.emit_line(f'ctx.{py_name} = args.{py_name}.lower() in ("true", "1", "yes", "t")')
            else:
                self.emit_line(f"ctx.{py_name} = args.{py_name}")
            self.indent_level -= 1

        self.emit_line("")
        self.emit_line("class MockSession:")
        self.indent_level += 1
        self.emit_line("def query(self, *args, **kwargs):")
        self.indent_level += 1
        self.emit_line("return []")
        self.indent_level -= 2
        self.emit_line("")
        self.emit_line("session = MockSession()")
        self.emit_line(f"result = {func_name}(ctx, session)")
        self.emit_line("")
        self.emit_line(f'print(f"[{func_name}] Execution complete:")')
        self.emit_line("for k, v in sorted(result.__dict__.items()):")
        self.indent_level += 1
        self.emit_line('if not k.startswith("_"):')
        self.indent_level += 1
        self.emit_line('print(f"  {k}: {v}")')
        self.indent_level -= 2

        redefined_syms = [s for s in unique_syms.values() if s.redefine_parent]
        for r_sym in sorted(redefined_syms, key=lambda s: s.redefine_offset):
            prop_name = self._clean_name(r_sym.name)
            self.emit_line(f'print(f"  {prop_name} (redefine): {{getattr(result, \'{prop_name}\')}}")')

        self.indent_level -= 1

    def generate(self, emit_main: bool = False) -> str:
        self.emit_line("from dataclasses import dataclass, field")
        self.emit_line("from decimal import Decimal")
        self.emit_line("from datetime import date, datetime, timedelta")

        orm_models = set()
        for op in self.module.operations:
            if isinstance(op, QueryIterationOp):
                orm_models.add(self._clean_name(op.entity).title().replace("_", ""))

        if orm_models:
            self.emit_line(f"from target_orm import {', '.join(sorted(orm_models))}")

        self.emit_line("")

        class_name = self._clean_name(self.module.module_id.replace("mod.", "")).title() + "Context"
        self.emit_line(f"class {class_name}:")
        self.indent_level += 1

        unique_syms = {s.id: s for s in self.module.symbols.values()}
        independent_syms = [s for s in unique_syms.values() if not s.redefine_parent]
        redefined_syms = [s for s in unique_syms.values() if s.redefine_parent]

        self.emit_line("def __init__(self):")
        self.indent_level += 1
        for sym in independent_syms:
            py_name = self._clean_name(sym.name)
            if sym.semantic_type.base == "decimal":
                default = "Decimal('0')"
            elif sym.semantic_type.base == "date":
                default = "date.today()"
            elif sym.semantic_type.base == "integer":
                default = "0"
            elif sym.semantic_type.base == "boolean":
                default = "False"
            else:
                default = '""'
            self.emit_line(f"self.{py_name} = {default}")
        if not independent_syms:
            self.emit_line("pass")
        self.indent_level -= 1
        self.emit_line("")

        for r_sym in sorted(redefined_syms, key=lambda s: s.redefine_offset):
            prop_name = self._clean_name(r_sym.name)
            parent_id = r_sym.redefine_parent
            parent_name = self._clean_name(parent_id.split(".")[-1])
            start_off = r_sym.redefine_offset
            length = r_sym.semantic_type.precision or r_sym.semantic_type.length or 2
            end_off = start_off + length

            self.emit_line("@property")
            self.emit_line(f"def {prop_name}(self) -> int:")
            self.indent_level += 1
            self.emit_line(f"sub = self.{parent_name}[{start_off}:{end_off}]")
            self.emit_line("return int(sub) if sub.isdigit() else 0")
            self.indent_level -= 1
            self.emit_line("")

            self.emit_line(f"@{prop_name}.setter")
            self.emit_line(f"def {prop_name}(self, val: int):")
            self.indent_level += 1
            self.emit_line(f"val_str = f'{{int(val):0{length}d}}'")
            self.emit_line(
                f"self.{parent_name} = self.{parent_name}[:{start_off}] + val_str + self.{parent_name}[{end_off}:]"
            )
            self.indent_level -= 1
            self.emit_line("")

        self.indent_level -= 1

        func_name = f"execute_{self._clean_name(self.module.module_id.replace('mod.', ''))}"
        self.emit_line(f"def {func_name}(ctx: {class_name}, session):")
        self.indent_level += 1
        for op in self.module.operations:
            self.emit_operation(op)
        if not self.module.operations:
            self.emit_line("pass")
        self.emit_line("return ctx")
        self.indent_level -= 1

        if emit_main:
            self.emit_main_block(class_name, func_name)

        return "\n".join(self.lines)
