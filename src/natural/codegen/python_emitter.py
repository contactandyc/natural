# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
#
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import List
from natural.ir.semantic import (
    SemanticModule, AssignOp, BranchOp, BreakOp,
    ContinueOp, ReturnOp, QueryIterationOp, SemanticExpression
)

class PythonEmitter:
    def __init__(self, module: SemanticModule):
        self.module = module
        self.indent_level = 0
        self.lines: List[str] = []

    def _clean_name(self, name: str) -> str:
        """Converts COBOL/Natural style names (#BASE-CHARGE) to Pythonic ones (base_charge)."""
        clean = name.replace("#", "").replace("-", "_").lower()
        if clean == "class":
            return "class_"
        return clean

    def _resolve_ref(self, symbol_id: str) -> str:
        """Resolves sym.local.base-charge -> ctx.base_charge."""
        parts = symbol_id.split('.')
        if len(parts) >= 3 and parts[1] in ("local", "parameter"):
            return f"ctx.{self._clean_name(parts[-1])}"
        elif len(parts) >= 3 and parts[1] == "entity":
            return f"record.{self._clean_name(parts[-1])}"
        elif len(parts) >= 3 and parts[1] == "unresolved":
            # REMOVED the inline # comment so it doesn't break Python syntax
            return f"ctx.{self._clean_name(parts[-1])}_UNRESOLVED"
        return symbol_id

    def emit_line(self, line: str):
        indent = "    " * self.indent_level
        self.lines.append(f"{indent}{line}")

    def emit_expr(self, expr: SemanticExpression) -> str:
        if expr.op == "ref" or expr.op == "entity_field":
            return self._resolve_ref(expr.symbol_id)
        elif expr.op == "literal":
            return repr(expr.value)
        elif expr.op in ("multiply", "add", "subtract", "divide", "gt", "lt", "eq", "gte", "lte"):
            op_map = {
                "multiply": "*", "add": "+", "subtract": "-", "divide": "/",
                "gt": ">", "lt": "<", "eq": "==", "gte": ">=", "lte": "<="
            }
            lhs = self.emit_expr(expr.lhs) if expr.lhs else ""
            rhs = self.emit_expr(expr.rhs) if expr.rhs else ""
            return f"({lhs} {op_map[expr.op]} {rhs})"
        return "None"

    def emit_operation(self, op):
        if isinstance(op, AssignOp):
            target = self._resolve_ref(op.target_id)
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

    def generate(self) -> str:
        # 1. Imports
        self.emit_line("from dataclasses import dataclass")
        self.emit_line("from decimal import Decimal")

        # Discover and emit ORM models used in this module
        orm_models = set()
        for op in self.module.operations:
            if isinstance(op, QueryIterationOp):
                orm_models.add(self._clean_name(op.entity).title().replace("_", ""))

        if orm_models:
            self.emit_line(f"from target_orm import {', '.join(sorted(orm_models))}")

        self.emit_line("")

        # 2. Data Context Class
        class_name = self._clean_name(self.module.module_id.replace("mod.", "")).title() + "Context"
        self.emit_line(f"@dataclass")
        self.emit_line(f"class {class_name}:")
        self.indent_level += 1

        # Python dataclasses require fields without defaults (parameters)
        # to precede fields with defaults (locals).
        params = [s for s in self.module.symbols.values() if s.scope == "parameter"]
        locals_ = [s for s in self.module.symbols.values() if s.scope == "local"]

        has_fields = False
        for sym in params + locals_:
            py_type = "Decimal" if sym.semantic_type.base == "decimal" else "str"

            if sym.scope == "local":
                default = "Decimal('0')" if py_type == "Decimal" else '""'
                self.emit_line(f"{self._clean_name(sym.name)}: {py_type} = {default}")
            else:
                self.emit_line(f"{self._clean_name(sym.name)}: {py_type}")
            has_fields = True

        if not has_fields:
            self.emit_line("pass")
        self.indent_level -= 1
        self.emit_line("")

        # 3. Main Function
        func_name = f"execute_{self._clean_name(self.module.module_id.replace('mod.', ''))}"
        self.emit_line(f"def {func_name}(ctx: {class_name}, session):")
        self.indent_level += 1
        for op in self.module.operations:
            self.emit_operation(op)
        if not self.module.operations:
            self.emit_line("pass")
        self.emit_line("return ctx")
        self.indent_level -= 1

        return "\n".join(self.lines)
