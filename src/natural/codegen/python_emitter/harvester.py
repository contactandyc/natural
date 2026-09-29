# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from decimal import Decimal
from typing import Dict, List, Set, Tuple
from natural.ir.semantic import (
    AssignOp,
    CallProgramOp,
    EntityGetOp,
    EntityStoreOp,
    FetchOp,
    QueryIterationOp,
    ReadWorkFileOp,
    TerminateOp,
)
from natural.codegen.python_emitter.context import EmitterContext


class ImportHarvester:
    """Harvests standard library, SQLAlchemy, ORM entity, and inter-module dependencies."""

    def __init__(self, ctx: EmitterContext):
        self.ctx = ctx

    def collect_required_imports(self, emit_main: bool = False) -> List[str]:
        needs_os = False
        needs_sys = False
        needs_decimal = False
        needs_round_half_up = False
        needs_date = False
        needs_datetime = False
        needs_timedelta = False

        for sym in self.ctx.module.symbols.values():
            if sym.scope == "entity_field":
                continue
            base = sym.semantic_type.base
            if base == "decimal":
                needs_decimal = True
            elif base == "date":
                needs_date = True

        for fn in self.ctx.module.functions.values():
            if fn.return_type.base == "decimal":
                needs_decimal = True
            elif fn.return_type.base == "date":
                needs_date = True
            for p in fn.parameters:
                if p.semantic_type.base == "decimal":
                    needs_decimal = True
                elif p.semantic_type.base == "date":
                    needs_date = True

        def scan_expr(expr):
            nonlocal needs_decimal, needs_date, needs_datetime, needs_timedelta
            if not expr:
                return
            if expr.op == "literal" and isinstance(expr.value, Decimal):
                needs_decimal = True
            if expr.op in ("sys_date",):
                needs_date = True
            elif expr.op in ("sys_time",):
                needs_datetime = True
            lhs_sym = self.ctx.get_symbol(expr.lhs.symbol_id) if (expr.lhs and expr.lhs.symbol_id) else None
            if lhs_sym and lhs_sym.semantic_type.base == "date" and expr.op in ("add", "subtract"):
                needs_timedelta = True
            scan_expr(expr.lhs)
            scan_expr(expr.rhs)
            for item in getattr(expr, "items", []):
                scan_expr(item)

        def scan_ops(ops):
            nonlocal needs_os, needs_sys, needs_decimal, needs_round_half_up, needs_date, needs_datetime
            for op in ops:
                if isinstance(op, ReadWorkFileOp):
                    needs_os = True
                if isinstance(op, TerminateOp):
                    needs_sys = True
                if isinstance(op, AssignOp):
                    target_sym = self.ctx.get_symbol(op.target_id)
                    source_sym = self.ctx.get_symbol(op.expr.symbol_id) if op.expr.symbol_id else None
                    if target_sym and target_sym.semantic_type.base in ("decimal", "numeric") and source_sym and source_sym.semantic_type.base == "string":
                        needs_decimal = True
                    if op.rounded:
                        if target_sym and target_sym.semantic_type.base == "decimal":
                            needs_decimal = True
                            needs_round_half_up = True
                    if op.edit_mask:
                        if (target_sym and target_sym.semantic_type.base == "date") or (source_sym and source_sym.semantic_type.base == "date"):
                            needs_datetime = True
                if hasattr(op, "expr"):
                    scan_expr(op.expr)
                if hasattr(op, "key_expr"):
                    scan_expr(op.key_expr)
                if hasattr(op, "condition"):
                    scan_expr(op.condition)
                if hasattr(op, "operands"):
                    for o in op.operands:
                        scan_expr(o)
                for sub_list in ("body", "then_branch", "else_branch"):
                    if hasattr(op, sub_list):
                        scan_ops(getattr(op, sub_list))

        scan_ops(self.ctx.module.operations)
        for sub in self.ctx.module.subroutines.values():
            scan_ops(sub.operations)
            if sub.on_error:
                scan_ops(sub.on_error.body)
        for fn in self.ctx.module.functions.values():
            scan_ops(fn.operations)

        if emit_main:
            for sym in self.ctx.module.symbols.values():
                if sym.redefine_parent or sym.scope == "entity_field":
                    continue
                if sym.semantic_type.base == "decimal":
                    needs_decimal = True
                elif sym.semantic_type.base == "date":
                    needs_date = True

        import_lines = []
        if needs_sys:
            import_lines.append("import sys")
        if needs_os:
            import_lines.append("import os")
        if needs_decimal:
            dec_imports = ["Decimal"]
            if needs_round_half_up:
                dec_imports.append("ROUND_HALF_UP")
            import_lines.append(f"from decimal import {', '.join(dec_imports)}")

        datetime_parts = []
        if needs_date:
            datetime_parts.append("date")
        if needs_datetime:
            datetime_parts.append("datetime")
        if needs_timedelta:
            datetime_parts.append("timedelta")

        if datetime_parts:
            import_lines.append(f"from datetime import {', '.join(sorted(datetime_parts))}")

        return import_lines

    def collect_module_metadata(self) -> Tuple[Dict[str, Set[str]], Set[str], bool]:
        callnat_imports: Dict[str, Set[str]] = {}
        orm_models = set()
        needs_func = False

        def walk_ops_for_metadata(ops):
            nonlocal needs_func
            for op in ops:
                if isinstance(op, (CallProgramOp, FetchOp)):
                    prog = self.ctx.clean_name(op.program_name)
                    if prog != self.ctx.clean_name(self.ctx.module.module_id):
                        if prog not in callnat_imports:
                            callnat_imports[prog] = set()
                        ctx_name = self.ctx.to_pascal_case(op.program_name) + "Context"
                        callnat_imports[prog].add(ctx_name)
                        callnat_imports[prog].add(f"execute_{prog}")
                elif isinstance(op, (QueryIterationOp, EntityStoreOp, EntityGetOp)):
                    orm_models.add(self.ctx.clean_name(op.entity).title().replace("_", ""))
                    if getattr(op, "cardinality", "") == "histogram":
                        needs_func = True

                for sub_list in ("body", "then_branch", "else_branch"):
                    if hasattr(op, sub_list):
                        walk_ops_for_metadata(getattr(op, sub_list))

        walk_ops_for_metadata(self.ctx.module.operations)
        for sub in self.ctx.module.subroutines.values():
            walk_ops_for_metadata(sub.operations)
            if sub.on_error:
                walk_ops_for_metadata(sub.on_error.body)
        for fn in self.ctx.module.functions.values():
            walk_ops_for_metadata(fn.operations)

        return callnat_imports, orm_models, needs_func
