# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from decimal import Decimal
from typing import List, Dict, Optional, Set
from natural.ir.semantic import (
    SemanticModule,
    Symbol,
    AssignOp,
    BranchOp,
    LoopOp,
    ForLoopOp,
    BreakOp,
    ContinueOp,
    ReturnOp,
    QueryIterationOp,
    SemanticExpression,
    CompressOp,
    ExamineOp,
    ResetOp,
    CallSubroutineOp,
    EntityUpdateOp,
    EntityStoreOp,
    EntityDeleteOp,
    ReadWorkFileOp,
    WriteWorkFileOp,
    CloseWorkFileOp,
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

    def _to_pascal_case(self, name: str) -> str:
        clean = name.split(".")[-1].replace("#", "").replace("-", "_").lower()
        return "".join(part.title() for part in clean.split("_") if part)

    def _resolve_ref(self, symbol_id: str, model_class: Optional[str] = None) -> str:
        parts = symbol_id.split(".")
        if len(parts) >= 3 and parts[1] in ("local", "parameter"):
            return f"ctx.{self._clean_name(parts[-1])}"
        elif len(parts) >= 3 and parts[1] == "entity":
            col_name = self._clean_name(parts[-1])
            if model_class:
                return f"{model_class}.{col_name}"
            return f"record.{col_name}"
        elif len(parts) >= 3 and parts[1] == "unresolved":
            return f"ctx.{self._clean_name(parts[-1])}_UNRESOLVED"
        return symbol_id

    def emit_line(self, line: str):
        if not line:
            self.lines.append("")
        else:
            indent = "    " * self.indent_level
            self.lines.append(f"{indent}{line}")

    def emit_expr(self, expr: SemanticExpression, model_class: Optional[str] = None) -> str:
        if expr.op in ("ref", "entity_field"):
            return self._resolve_ref(expr.symbol_id, model_class=model_class)
        elif expr.op == "literal":
            if isinstance(expr.value, Decimal):
                return f"Decimal('{expr.value}')"
            return repr(expr.value)
        elif expr.op == "counter":
            return str(expr.value)
        elif expr.op == "sys_date":
            return "date.today()"
        elif expr.op == "sys_time":
            return "datetime.now().time()"
        elif expr.op in ("multiply", "add", "subtract", "divide", "gt", "lt", "eq", "gte", "lte", "neq", "and", "or"):
            op_map = {
                "multiply": "*", "add": "+", "subtract": "-", "divide": "/",
                "gt": ">", "lt": "<", "eq": "==", "gte": ">=", "lte": "<=", "neq": "!=",
                "and": "and", "or": "or",
            }
            lhs_sym = self._sym_by_id.get(expr.lhs.symbol_id) if (expr.lhs and expr.lhs.symbol_id) else None
            if lhs_sym and lhs_sym.semantic_type.base == "date" and expr.op in ("add", "subtract"):
                lhs = self.emit_expr(expr.lhs, model_class=model_class)
                rhs_val = expr.rhs.value if expr.rhs else 1
                op = "+" if expr.op == "add" else "-"
                return f"({lhs} {op} timedelta(days={rhs_val}))"

            lhs = self.emit_expr(expr.lhs, model_class=model_class) if expr.lhs else ""
            rhs = self.emit_expr(expr.rhs, model_class=model_class) if expr.rhs else ""
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

        elif isinstance(op, CompressOp):
            target = self._resolve_ref(op.target_id)
            sep = f"{self.emit_expr(op.delimiter)}" if op.delimiter else "''"
            items_str = ", ".join(f"str({self.emit_expr(e)})" for e in op.operands)
            self.emit_line(f"{target} = {sep}.join([{items_str}])")

        elif isinstance(op, ExamineOp):
            target = self._resolve_ref(op.target_id)
            pattern = self.emit_expr(op.pattern)
            if op.replace_with:
                rep = self.emit_expr(op.replace_with)
                self.emit_line(f"{target} = {target}.replace(str({pattern}), str({rep}))")
            elif op.giving_number_id:
                count_var = self._resolve_ref(op.giving_number_id)
                self.emit_line(f"{count_var} = {target}.count(str({pattern}))")

        elif isinstance(op, ResetOp):
            target = self._resolve_ref(op.target_id)
            sym = self._sym_by_id.get(op.target_id)
            if sym and sym.semantic_type.base == "decimal":
                default = "Decimal('0')"
            elif sym and sym.semantic_type.base == "integer":
                default = "0"
            elif sym and sym.semantic_type.base == "boolean":
                default = "False"
            else:
                default = '""'
            self.emit_line(f"{target} = {default}")

        elif isinstance(op, CallSubroutineOp):
            clean_sub = self._clean_name(op.subroutine_name)
            self.emit_line(f"sub_{clean_sub}(ctx, session)")

        elif isinstance(op, EntityUpdateOp):
            self.emit_line("session.flush()  # UPDATE committed for active loop")

        elif isinstance(op, EntityStoreOp):
            model_name = self._clean_name(op.entity).title().replace("_", "")
            self.emit_line(f"new_record = {model_name}()")
            self.emit_line("session.add(new_record)")
            self.emit_line("session.flush()  # STORE committed")

        elif isinstance(op, EntityDeleteOp):
            self.emit_line("session.delete(record)")
            self.emit_line("session.flush()  # DELETE committed")

        elif isinstance(op, WriteWorkFileOp):
            items_str = ", ".join(f"str({self.emit_expr(e)})" for e in op.operands)
            self.emit_line(f'with open(f"workfile_{op.file_number}.dat", "a", encoding="utf-8") as wf:')
            self.indent_level += 1
            self.emit_line(f'wf.write("\\t".join([{items_str}]) + "\\n")')
            self.indent_level -= 1

        elif isinstance(op, CloseWorkFileOp):
            self.emit_line(f"# CLOSE WORK FILE {op.file_number}")

        elif isinstance(op, ReadWorkFileOp):
            self.emit_line(f'if os.path.exists("workfile_{op.file_number}.dat"):')
            self.indent_level += 1
            self.emit_line(f'with open("workfile_{op.file_number}.dat", "r", encoding="utf-8") as wf:')
            self.indent_level += 1
            self.emit_line("for line in wf:")
            self.indent_level += 1
            self.emit_line("parts = line.rstrip('\\n').split('\\t')")
            for idx, target_id in enumerate(op.target_ids):
                target_var = self._resolve_ref(target_id)
                self.emit_line(f"if len(parts) > {idx}:")
                self.indent_level += 1
                self.emit_line(f"{target_var} = parts[{idx}]")
                self.indent_level -= 1
            if not op.body:
                self.emit_line("pass")
            for sub_op in op.body:
                self.emit_operation(sub_op)
            self.indent_level -= 3

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

        elif isinstance(op, ForLoopOp):
            var_target = self._resolve_ref(op.variable_id)
            start_val = self.emit_expr(op.start)
            end_val = self.emit_expr(op.end)
            step_val = self.emit_expr(op.step)
            self.emit_line(f"for loop_val in range(int({start_val}), int({end_val}) + 1, int({step_val})):")
            self.indent_level += 1
            self.emit_line(f"{var_target} = loop_val")
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
            cond = self.emit_expr(op.predicate, model_class=model_name)
            limit_clause = f".limit({op.limit})" if getattr(op, "limit", None) else ""
            self.emit_line(f"for loop_idx, record in enumerate(session.query({model_name}).filter({cond}){limit_clause}, 1):")
            self.indent_level += 1
            self.emit_line("loop_counter = loop_idx")
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
        independent_syms = [
            s for s in unique_syms.values()
            if not s.redefine_parent and s.scope != "entity_field"
        ]
        for sym in independent_syms:
            py_name = self._clean_name(sym.name)
            arg_flag = f"--{py_name}"
            self.emit_line(f'parser.add_argument("{arg_flag}", type=str, default=None, help="Initial value for {py_name}")')

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
        self.emit_line("class MockQuery(list):")
        self.indent_level += 1
        self.emit_line("def filter(self, *args, **kwargs):")
        self.indent_level += 1
        self.emit_line("return self")
        self.indent_level -= 1
        self.emit_line("def limit(self, *args, **kwargs):")
        self.indent_level += 1
        self.emit_line("return self")
        self.indent_level -= 2
        self.emit_line("")
        self.emit_line("class MockSession:")
        self.indent_level += 1
        self.emit_line("def query(self, *args, **kwargs):")
        self.indent_level += 1
        self.emit_line("return MockQuery()")
        self.indent_level -= 1
        self.emit_line("def add(self, obj): pass")
        self.emit_line("def delete(self, obj): pass")
        self.emit_line("def flush(self):")
        self.indent_level += 1
        self.emit_line("pass")
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

    def _collect_required_imports(self, emit_main: bool = False) -> List[str]:
        """Inspects symbols and operations to emit only strictly required imports."""
        needs_os = False
        needs_decimal = False
        needs_date = False
        needs_datetime = False
        needs_timedelta = False

        # 1. Inspect symbols
        for sym in self.module.symbols.values():
            base = sym.semantic_type.base
            if base == "decimal":
                needs_decimal = True
            elif base == "date":
                needs_date = True

        # 2. Inspect operations recursively
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
            lhs_sym = self._sym_by_id.get(expr.lhs.symbol_id) if (expr.lhs and expr.lhs.symbol_id) else None
            if lhs_sym and lhs_sym.semantic_type.base == "date" and expr.op in ("add", "subtract"):
                needs_timedelta = True
            scan_expr(expr.lhs)
            scan_expr(expr.rhs)
            for item in getattr(expr, "items", []):
                scan_expr(item)

        def scan_ops(ops):
            nonlocal needs_os, needs_decimal, needs_date, needs_datetime
            for op in ops:
                if isinstance(op, ReadWorkFileOp):
                    needs_os = True
                if isinstance(op, AssignOp) and op.edit_mask:
                    needs_datetime = True
                if hasattr(op, "expr"):
                    scan_expr(op.expr)
                if hasattr(op, "condition"):
                    scan_expr(op.condition)
                if hasattr(op, "operands"):
                    for o in op.operands:
                        scan_expr(o)
                for sub_list in ("body", "then_branch", "else_branch"):
                    if hasattr(op, sub_list):
                        scan_ops(getattr(op, sub_list))

        scan_ops(self.module.operations)
        for sub in self.module.subroutines.values():
            scan_ops(sub.operations)

        # 3. Inspect main block requirements
        if emit_main:
            for sym in self.module.symbols.values():
                if sym.redefine_parent or sym.scope == "entity_field":
                    continue
                if sym.semantic_type.base == "decimal":
                    needs_decimal = True
                elif sym.semantic_type.base == "date":
                    needs_date = True

        import_lines = []
        if needs_os:
            import_lines.append("import os")
        if needs_decimal:
            import_lines.append("from decimal import Decimal")

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

    def generate(self, emit_main: bool = False) -> str:
        # Dynamic imports based on actual usage
        import_lines = self._collect_required_imports(emit_main=emit_main)
        for imp in import_lines:
            self.emit_line(imp)

        orm_models = set()
        for op in self.module.operations:
            if isinstance(op, (QueryIterationOp, EntityStoreOp)):
                orm_models.add(self._clean_name(op.entity).title().replace("_", ""))

        if orm_models:
            self.emit_line(f"from target_orm import {', '.join(sorted(orm_models))}")

        if import_lines or orm_models:
            self.emit_line("")

        class_name = self._to_pascal_case(self.module.module_id) + "Context"
        self.emit_line(f"class {class_name}:")
        self.indent_level += 1

        unique_syms = {s.id: s for s in self.module.symbols.values()}
        independent_syms = [
            s for s in unique_syms.values()
            if not s.redefine_parent and s.scope != "entity_field"
        ]
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

        for sub_name, sub_block in self.module.subroutines.items():
            sub_func = f"sub_{self._clean_name(sub_name)}"
            self.emit_line(f"def {sub_func}(ctx: {class_name}, session):")
            self.indent_level += 1
            for op in sub_block.operations:
                self.emit_operation(op)
            if not sub_block.operations:
                self.emit_line("pass")
            self.emit_line("return ctx")
            self.indent_level -= 1
            self.emit_line("")

        func_name = f"execute_{self._clean_name(self.module.module_id)}"
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
