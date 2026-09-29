# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from decimal import Decimal, ROUND_HALF_UP
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
    SeparateOp,
    ExamineOp,
    MoveAllOp,
    ResetOp,
    CallSubroutineOp,
    CallProgramOp,
    FetchOp,
    TransactionOp,
    EntityRefreshOp,
    TerminateOp,
    AtStartOfDataOp,
    AtEndOfDataOp,
    AtBreakOp,
    ResizeArrayOp,
    EntityUpdateOp,
    EntityStoreOp,
    EntityDeleteOp,
    ReadWorkFileOp,
    WriteWorkFileOp,
    CloseWorkFileOp,
    OnErrorOp,
    FunctionBlockOp,
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

    def _clean_func_name(self, name: str) -> str:
        clean = name.replace("#", "_").replace("-", "_").lower()
        while clean.startswith("fn_") or clean.startswith("f_") or clean.startswith("udf_"):
            if clean.startswith("fn_"):
                clean = clean[3:]
            elif clean.startswith("f_"):
                clean = clean[2:]
            elif clean.startswith("udf_"):
                clean = clean[4:]
        return f"fn_{clean}"

    def _to_pascal_case(self, name: str) -> str:
        clean = name.split(".")[-1].replace("#", "").replace("-", "_").lower()
        return "".join(part.title() for part in clean.split("_") if part)

    def _resolve_ref(self, symbol_id: str, model_class: Optional[str] = None) -> str:
        if symbol_id.startswith("record."):
            return symbol_id
        parts = symbol_id.split(".")
        if len(parts) >= 3 and parts[0] == "fn":
            return self._clean_name(parts[-1])
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
            base_ref = self._resolve_ref(expr.symbol_id, model_class=model_class)
            if getattr(expr, "array_indices", None):
                for idx in expr.array_indices:
                    idx_val = self.emit_expr(idx, model_class=model_class)
                    base_ref = f"{base_ref}[({idx_val} - 1)]"
            if expr.substring:
                start_val = self.emit_expr(expr.substring.start, model_class=model_class)
                if expr.substring.length:
                    len_val = self.emit_expr(expr.substring.length, model_class=model_class)
                    return f"{base_ref}[({start_val} - 1):({start_val} - 1) + {len_val}]"
                return f"{base_ref}[({start_val} - 1):]"
            return base_ref
        elif expr.op == "func_call":
            fn_name = self._clean_func_name(expr.symbol_id or "func")
            args_str = ", ".join(self.emit_expr(it, model_class=model_class) for it in expr.items)
            return f"{fn_name}({args_str})"
        elif expr.op == "tuple":
            items = ", ".join(self.emit_expr(it, model_class=model_class) for it in expr.items)
            return f"({items})"
        elif expr.op == "not":
            inner = self.emit_expr(expr.lhs, model_class=model_class)
            return f"(not {inner})"
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
        elif expr.op in ("multiply", "add", "subtract", "divide", "modulo", "power", "gt", "lt", "eq", "gte", "lte", "neq", "and", "or"):
            op_map = {
                "multiply": "*", "add": "+", "subtract": "-", "divide": "/",
                "modulo": "%", "power": "**",
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

    def _format_numeric_edit_mask(self, target: str, src_ref: str, mask: str) -> str:
        raw_mask = mask.strip().upper()

        has_currency = "$" in raw_mask
        prefix = "$" if has_currency else ""
        cleaned = raw_mask.replace("$", "").strip()

        suffix_token = None
        if cleaned.endswith("CR"):
            suffix_token = "CR"
            cleaned = cleaned[:-2].strip()
        elif cleaned.endswith("DB"):
            suffix_token = "DB"
            cleaned = cleaned[:-2].strip()
        elif cleaned.endswith("-"):
            suffix_token = "-"
            cleaned = cleaned[:-1].strip()
        elif cleaned.endswith("+"):
            suffix_token = "+"
            cleaned = cleaned[:-1].strip()

        prefix_sign = None
        if not suffix_token:
            if cleaned.startswith("+"):
                prefix_sign = "+"
                cleaned = cleaned[1:].strip()
            elif cleaned.startswith("-"):
                prefix_sign = "-"
                cleaned = cleaned[1:].strip()

        decimals = 0
        if "." in cleaned:
            int_part, dec_part = cleaned.split(".", 1)
            decimals = len(dec_part)
        else:
            int_part = cleaned

        use_comma = "," in int_part
        has_zero_suppression = int_part.count("Z") > 0
        total_num_width = len(int_part) + (1 + decimals if decimals > 0 else 0)

        is_fixed_column = has_currency or suffix_token in ("CR", "DB")
        if is_fixed_column and has_zero_suppression:
            fmt_spec = f">{total_num_width},.{decimals}f" if use_comma else f">{total_num_width}.{decimals}f"
            pos_padding = "  " if suffix_token in ("CR", "DB") else (" " if suffix_token in ("-", "+") else "")
        else:
            fmt_spec = f",.{decimals}f" if use_comma else f".{decimals}f"
            pos_padding = ""

        value_expr = f"abs({src_ref})" if (suffix_token or prefix_sign) else src_ref

        suffix_code = ""
        if suffix_token == "CR":
            suffix_code = f"{{'CR' if {src_ref} < 0 else '{pos_padding}'}}"
        elif suffix_token == "DB":
            suffix_code = f"{{'DB' if {src_ref} < 0 else '{pos_padding}'}}"
        elif suffix_token == "-":
            suffix_code = f"{{'-' if {src_ref} < 0 else '{pos_padding}'}}"
        elif suffix_token == "+":
            suffix_code = f"{{'-' if {src_ref} < 0 else '+'}}"

        prefix_code = prefix
        if prefix_sign == "+":
            prefix_code += f"{{'-' if {src_ref} < 0 else '+'}}"
        elif prefix_sign == "-":
            prefix_code += f"{{'-' if {src_ref} < 0 else ' '}}"

        return f"{target} = f\"{prefix_code}{{{value_expr}:{fmt_spec}}}{suffix_code}\""

    def emit_operation(self, op):
        if isinstance(op, AssignOp):
            target = self._resolve_ref(op.target_id)
            if getattr(op, "target_indices", None):
                for idx in op.target_indices:
                    idx_val = self.emit_expr(idx)
                    target = f"{target}[({idx_val} - 1)]"

            target_sym = self._sym_by_id.get(op.target_id)
            source_sym = self._sym_by_id.get(op.expr.symbol_id) if op.expr.symbol_id else None

            if op.target_substring:
                start_val = self.emit_expr(op.target_substring.start)
                s_idx = f"({start_val} - 1)"
                if op.target_substring.length:
                    len_val = self.emit_expr(op.target_substring.length)
                    e_idx = f"({s_idx} + {len_val})"
                else:
                    e_idx = "None"
                rhs_val = f"str({self.emit_expr(op.expr)})"
                self.emit_line(f"{target} = {target}[:{s_idx}] + {rhs_val} + ({target}[{e_idx}:] if {e_idx} is not None else '')")
                return

            if op.edit_mask and target_sym and source_sym:
                if target_sym.semantic_type.base == "string" and source_sym.semantic_type.base == "date":
                    py_mask = self._convert_edit_mask(op.edit_mask)
                    self.emit_line(f"{target} = {self._resolve_ref(op.expr.symbol_id)}.strftime('{py_mask}')")
                    return
                elif target_sym.semantic_type.base == "date" and source_sym.semantic_type.base == "string":
                    py_mask = self._convert_edit_mask(op.edit_mask)
                    self.emit_line(f"{target} = datetime.strptime({self._resolve_ref(op.expr.symbol_id)}, '{py_mask}').date()")
                    return
                elif target_sym.semantic_type.base == "string" and source_sym.semantic_type.base in ("decimal", "integer", "numeric"):
                    src_ref = self._resolve_ref(op.expr.symbol_id)
                    formatted_line = self._format_numeric_edit_mask(target, src_ref, op.edit_mask)
                    self.emit_line(formatted_line)
                    return
                elif target_sym.semantic_type.base in ("decimal", "numeric") and source_sym.semantic_type.base == "string":
                    src_ref = self._resolve_ref(op.expr.symbol_id)
                    self.emit_line(f"_val = {src_ref}.strip().replace('$', '').replace(',', '').replace(' ', '').replace('+', '')")
                    self.emit_line(f"_is_neg = _val.endswith('-') or _val.startswith('-') or _val.endswith(('CR', 'DB')) or (_val.startswith('(') and _val.endswith(')'))")
                    self.emit_line(f"_num = _val.rstrip('-CRDBcrdb').lstrip('-+(').rstrip(')').strip()")
                    self.emit_line(f"{target} = -Decimal(_num) if _is_neg else (Decimal(_num) if _num else Decimal('0'))")
                    return
                elif target_sym.semantic_type.base == "integer" and source_sym.semantic_type.base == "string":
                    src_ref = self._resolve_ref(op.expr.symbol_id)
                    self.emit_line(f"_val = {src_ref}.strip().replace('$', '').replace(',', '').replace(' ', '').replace('+', '')")
                    self.emit_line(f"_is_neg = _val.endswith('-') or _val.startswith('-') or _val.endswith(('CR', 'DB')) or (_val.startswith('(') and _val.endswith(')'))")
                    self.emit_line(f"_num = _val.rstrip('-CRDBcrdb').lstrip('-+(').rstrip(')').strip()")
                    self.emit_line(f"{target} = -int(_num) if _is_neg else (int(_num) if _num else 0)")
                    return

            if target_sym and target_sym.semantic_type.base in ("decimal", "numeric") and source_sym and source_sym.semantic_type.base == "string":
                src_ref = self._resolve_ref(op.expr.symbol_id)
                self.emit_line(f"_val = {src_ref}.strip().replace('$', '').replace(',', '').replace(' ', '').replace('+', '')")
                self.emit_line(f"_is_neg = _val.endswith('-') or _val.startswith('-') or _val.endswith(('CR', 'DB')) or (_val.startswith('(') and _val.endswith(')'))")
                self.emit_line(f"_num = _val.rstrip('-CRDBcrdb').lstrip('-+(').rstrip(')').strip()")
                self.emit_line(f"{target} = -Decimal(_num) if _is_neg else (Decimal(_num) if _num else Decimal('0'))")
                return

            expr = self.emit_expr(op.expr)
            if op.rounded and target_sym and target_sym.semantic_type.base == "decimal":
                scale = target_sym.semantic_type.scale or 0
                quant = f"Decimal('1e-{scale}')" if scale > 0 else "Decimal('1')"
                self.emit_line(f"{target} = ({expr}).quantize({quant}, rounding=ROUND_HALF_UP)")
            elif op.rounded and target_sym and target_sym.semantic_type.base == "integer":
                self.emit_line(f"{target} = int(round({expr}))")
            elif target_sym and target_sym.semantic_type.base == "integer":
                if op.expr.op == "divide":
                    self.emit_line(f"{target} = int({expr})")
                else:
                    self.emit_line(f"{target} = {expr}")
            else:
                self.emit_line(f"{target} = {expr}")

        elif isinstance(op, MoveAllOp):
            target = self._resolve_ref(op.target_id)
            sym = self._sym_by_id.get(op.target_id)
            length = sym.semantic_type.length if sym and sym.semantic_type.length else f"len({target})"
            fill = self.emit_expr(op.fill_char)
            self.emit_line(f"{target} = str({fill}) * {length}")

        elif isinstance(op, CompressOp):
            target = self._resolve_ref(op.target_id)
            if op.leaving_no_space:
                sep = "''"
            elif op.delimiter:
                sep = f"{self.emit_expr(op.delimiter)}"
            else:
                sep = "' '"
            items_str = ", ".join(f"str({self.emit_expr(e)})" for e in op.operands)
            self.emit_line(f"{target} = {sep}.join([{items_str}])")

        elif isinstance(op, SeparateOp):
            source = self.emit_expr(op.source)
            delimiter_code = f"str({self.emit_expr(op.delimiter)})" if op.delimiter else "None"
            maxsplit = len(op.target_ids) - 1 if op.ignore_remainder else -1
            self.emit_line(f"_parts = {source}.split({delimiter_code}, {maxsplit})")
            for idx, target_id in enumerate(op.target_ids):
                target_var = self._resolve_ref(target_id)
                self.emit_line(f"{target_var} = _parts[{idx}] if len(_parts) > {idx} else ''")

        elif isinstance(op, ExamineOp):
            target = self._resolve_ref(op.target_id)
            if op.translate_case == "UPPER":
                self.emit_line(f"{target} = {target}.upper()")
            elif op.translate_case == "LOWER":
                self.emit_line(f"{target} = {target}.lower()")
            elif op.replace_with:
                pattern = self.emit_expr(op.pattern)
                rep = self.emit_expr(op.replace_with)
                self.emit_line(f"{target} = {target}.replace(str({pattern}), str({rep}))")
            elif op.giving_number_id:
                pattern = self.emit_expr(op.pattern)
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

        elif isinstance(op, CallProgramOp):
            prog_clean = self._clean_name(op.program_name)
            sub_ctx_class = self._to_pascal_case(op.program_name) + "Context"
            sub_ctx_var = f"_{prog_clean}_ctx"

            self.emit_line(f"{sub_ctx_var} = {sub_ctx_class}()")
            for b in op.bindings:
                val_expr = self.emit_expr(b.caller_expr)
                callee_prop = self._clean_name(b.callee_field)
                self.emit_line(f"{sub_ctx_var}.{callee_prop} = {val_expr}")

            self.emit_line(f"execute_{prog_clean}({sub_ctx_var}, session)")

            for b in op.bindings:
                if b.is_lvalue and b.caller_target_id:
                    caller_var = self._resolve_ref(b.caller_target_id)
                    callee_prop = self._clean_name(b.callee_field)
                    self.emit_line(f"{caller_var} = {sub_ctx_var}.{callee_prop}")

        elif isinstance(op, FetchOp):
            prog_clean = self._clean_name(op.program_name)
            sub_ctx_class = self._to_pascal_case(op.program_name) + "Context"
            sub_ctx_var = f"_{prog_clean}_ctx"

            self.emit_line(f"{sub_ctx_var} = {sub_ctx_class}()")
            for b in op.bindings:
                val_expr = self.emit_expr(b.caller_expr)
                callee_prop = self._clean_name(b.callee_field)
                self.emit_line(f"{sub_ctx_var}.{callee_prop} = {val_expr}")

            self.emit_line(f"execute_{prog_clean}({sub_ctx_var}, session)")

            for b in op.bindings:
                if b.is_lvalue and b.caller_target_id:
                    caller_var = self._resolve_ref(b.caller_target_id)
                    callee_prop = self._clean_name(b.callee_field)
                    self.emit_line(f"{caller_var} = {sub_ctx_var}.{callee_prop}")

            if not op.returning:
                self.emit_line("return ctx")

        elif isinstance(op, TransactionOp):
            if op.action == "commit":
                self.emit_line("session.commit()")
            else:
                self.emit_line("session.rollback()")

        elif isinstance(op, EntityRefreshOp):
            self.emit_line("session.refresh(record)")

        elif isinstance(op, TerminateOp):
            self.emit_line("sys.exit(0)")

        elif isinstance(op, AtStartOfDataOp):
            self.emit_line("if loop_idx == 1:")
            self.indent_level += 1
            if not op.body:
                self.emit_line("pass")
            for sub_op in op.body:
                self.emit_operation(sub_op)
            self.indent_level -= 1

        elif isinstance(op, AtEndOfDataOp):
            self.emit_line("if loop_counter > 0:")
            self.indent_level += 1
            if not op.body:
                self.emit_line("pass")
            for sub_op in op.body:
                self.emit_operation(sub_op)
            self.indent_level -= 1

        elif isinstance(op, AtBreakOp):
            if op.field_name:
                field_ref = self._resolve_ref(op.field_name)
                clean_f = self._clean_name(op.field_name)
                self.emit_line(f"if _prev_{clean_f} is not None and {field_ref} != _prev_{clean_f}:")
                self.indent_level += 1
                if not op.body:
                    self.emit_line("pass")
                for sub_op in op.body:
                    self.emit_operation(sub_op)
                self.indent_level -= 1
            else:
                for sub_op in op.body:
                    self.emit_operation(sub_op)

        elif isinstance(op, ResizeArrayOp):
            target = self._resolve_ref(op.target_id)
            size = self.emit_expr(op.size)
            self.emit_line(f"{target} = [None] * int({size})")

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
            if op.loop_type in ("until", "until_post") and op.condition:
                cond = self.emit_expr(op.condition)
                self.emit_line("while True:")
                self.indent_level += 1
                if not op.body:
                    self.emit_line("pass")
                for sub_op in op.body:
                    self.emit_operation(sub_op)
                self.emit_line(f"if {cond}:")
                self.indent_level += 1
                self.emit_line("break")
                self.indent_level -= 1
                self.indent_level -= 1
            elif op.loop_type == "while" and op.condition:
                cond = self.emit_expr(op.condition)
                self.emit_line(f"while {cond}:")
                self.indent_level += 1
                if not op.body:
                    self.emit_line("pass")
                for sub_op in op.body:
                    self.emit_operation(sub_op)
                self.indent_level -= 1
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
            if op.expr:
                self.emit_line(f"return {self.emit_expr(op.expr)}")
            else:
                self.emit_line("return ctx")

        elif isinstance(op, QueryIterationOp):
            model_name = self._clean_name(op.entity).title().replace("_", "")
            limit_clause = f".limit({op.limit})" if getattr(op, "limit", None) else ""

            if getattr(op, "cardinality", "") == "histogram":
                col_name = self._clean_name(op.descriptor or "id")
                cond = self.emit_expr(op.predicate, model_class=model_name)
                filter_clause = f".filter({cond})" if cond != "True" else ""
                self.emit_line(
                    f"for loop_idx, record in enumerate(session.query({model_name}.{col_name}.label('{col_name}'), func.count({model_name}.{col_name}).label('number')){filter_clause}.group_by({model_name}.{col_name}){limit_clause}, 1):"
                )
                self.indent_level += 1
                self.emit_line("loop_counter = loop_idx")
                if not op.body:
                    self.emit_line("pass")
                for sub_op in op.body:
                    self.emit_operation(sub_op)
                self.indent_level -= 1
                return

            cond = self.emit_expr(op.predicate, model_class=model_name)

            break_ops = [sub for sub in op.body if isinstance(sub, AtBreakOp) and sub.field_name]
            for b_op in break_ops:
                clean_f = self._clean_name(b_op.field_name)
                self.emit_line(f"_prev_{clean_f} = None")

            self.emit_line(f"for loop_idx, record in enumerate(session.query({model_name}).filter({cond}){limit_clause}, 1):")
            self.indent_level += 1
            self.emit_line("loop_counter = loop_idx")
            if not op.body:
                self.emit_line("pass")
            for sub_op in op.body:
                self.emit_operation(sub_op)

            for b_op in break_ops:
                clean_f = self._clean_name(b_op.field_name)
                field_ref = self._resolve_ref(b_op.field_name)
                self.emit_line(f"_prev_{clean_f} = {field_ref}")

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
            kebab_flag = f"--{py_name.replace('_', '-')}"
            snake_flag = f"--{py_name}"
            if kebab_flag != snake_flag:
                flags = f'"{kebab_flag}", "{snake_flag}"'
            else:
                flags = f'"{kebab_flag}"'

            self.emit_line(
                f'parser.add_argument({flags}, dest="{py_name}", type=str, default=None, help="Initial value for {py_name}")'
            )

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
        self.indent_level -= 1
        self.emit_line("def group_by(self, *args, **kwargs):")
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
        self.emit_line("def flush(self): pass")
        self.emit_line("def commit(self): pass")
        self.emit_line("def rollback(self): pass")
        self.emit_line("def refresh(self, obj): pass")
        self.indent_level -= 1
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
        needs_os = False
        needs_sys = False
        needs_decimal = False
        needs_round_half_up = False
        needs_date = False
        needs_datetime = False
        needs_timedelta = False

        for sym in self.module.symbols.values():
            if sym.scope == "entity_field":
                continue
            base = sym.semantic_type.base
            if base == "decimal":
                needs_decimal = True
            elif base == "date":
                needs_date = True

        for fn in self.module.functions.values():
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
            lhs_sym = self._sym_by_id.get(expr.lhs.symbol_id) if (expr.lhs and expr.lhs.symbol_id) else None
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
                    target_sym = self._sym_by_id.get(op.target_id)
                    source_sym = self._sym_by_id.get(op.expr.symbol_id) if op.expr.symbol_id else None
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
        for fn in self.module.functions.values():
            scan_ops(fn.operations)

        if emit_main:
            for sym in self.module.symbols.values():
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

    def _type_to_python_hint(self, sem_type: SemanticType) -> str:
        base = sem_type.base
        if base == "decimal":
            return "Decimal"
        elif base == "integer":
            return "int"
        elif base == "string":
            return "str"
        elif base == "boolean":
            return "bool"
        elif base == "date":
            return "date"
        return "Any"

    def generate(self, emit_main: bool = False) -> str:
        import_lines = self._collect_required_imports(emit_main=emit_main)
        for imp in import_lines:
            self.emit_line(imp)

        callnat_imports: Dict[str, Set[str]] = {}
        orm_models = set()
        needs_func = False

        def walk_ops_for_metadata(ops):
            nonlocal needs_func
            for op in ops:
                if isinstance(op, (CallProgramOp, FetchOp)):
                    prog = self._clean_name(op.program_name)
                    if prog != self._clean_name(self.module.module_id):
                        if prog not in callnat_imports:
                            callnat_imports[prog] = set()
                        ctx_name = self._to_pascal_case(op.program_name) + "Context"
                        callnat_imports[prog].add(ctx_name)
                        callnat_imports[prog].add(f"execute_{prog}")
                elif isinstance(op, (QueryIterationOp, EntityStoreOp)):
                    orm_models.add(self._clean_name(op.entity).title().replace("_", ""))
                    if getattr(op, "cardinality", "") == "histogram":
                        needs_func = True

                for sub_list in ("body", "then_branch", "else_branch"):
                    if hasattr(op, sub_list):
                        walk_ops_for_metadata(getattr(op, sub_list))

        walk_ops_for_metadata(self.module.operations)
        for sub in self.module.subroutines.values():
            walk_ops_for_metadata(sub.operations)
        for fn in self.module.functions.values():
            walk_ops_for_metadata(fn.operations)

        for prog in sorted(callnat_imports):
            items = ", ".join(sorted(callnat_imports[prog]))
            self.emit_line(f"from {prog} import {items}")

        if needs_func:
            self.emit_line("from sqlalchemy import func")
        if orm_models:
            self.emit_line(f"from target_orm import {', '.join(sorted(orm_models))}")

        if import_lines or callnat_imports or orm_models or needs_func:
            self.emit_line("")

        # Emit user-defined functions
        for fn_name, fn_block in self.module.functions.items():
            py_fn_name = self._clean_func_name(fn_name)
            params_list = [f"{self._clean_name(p.name)}: {self._type_to_python_hint(p.semantic_type)}" for p in fn_block.parameters]
            ret_hint = self._type_to_python_hint(fn_block.return_type)
            self.emit_line(f"def {py_fn_name}({', '.join(params_list)}) -> {ret_hint}:")
            self.indent_level += 1
            if not fn_block.operations:
                self.emit_line("pass")
            for op in fn_block.operations:
                self.emit_operation(op)
            self.indent_level -= 1
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

        on_error_op = next((op for op in self.module.operations if isinstance(op, OnErrorOp)), None)
        other_ops = [op for op in self.module.operations if not isinstance(op, OnErrorOp)]

        if on_error_op:
            self.emit_line("try:")
            self.indent_level += 1
            if not other_ops:
                self.emit_line("pass")
            for op in other_ops:
                self.emit_operation(op)
            self.indent_level -= 1
            self.emit_line("except Exception as natural_err:")
            self.indent_level += 1
            if not on_error_op.body:
                self.emit_line("pass")
            for op in on_error_op.body:
                self.emit_operation(op)
            self.indent_level -= 1
        else:
            for op in other_ops:
                self.emit_operation(op)
            if not other_ops:
                self.emit_line("pass")

        self.emit_line("return ctx")
        self.indent_level -= 1

        if emit_main:
            self.emit_main_block(class_name, func_name)

        return "\n".join(self.lines)
