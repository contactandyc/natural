# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from decimal import Decimal
from typing import Optional
from natural.ir.semantic import SemanticExpression
from natural.codegen.targets.python.context import EmitterContext


class PythonExpressionEmitter:
    """Emits SemanticExpression trees into valid Python code."""

    def __init__(self, ctx: EmitterContext):
        self.ctx = ctx

    def emit_expr(self, expr: SemanticExpression, model_class: Optional[str] = None) -> str:
        if expr.op in ("ref", "entity_field"):
            base_ref = self.ctx.resolve_ref(expr.symbol_id, model_class=model_class)
            if getattr(expr, "array_indices", None):
                for idx in expr.array_indices:
                    if idx.op == "literal" and isinstance(idx.value, int):
                        base_ref = f"{base_ref}[{idx.value - 1}]"
                    else:
                        idx_val = self.emit_expr(idx, model_class=model_class)
                        base_ref = f"{base_ref}[({idx_val} - 1)]"
            if expr.substring:
                start_val = self.emit_expr(expr.substring.start, model_class=model_class)
                s_idx = f"({start_val} - 1)"
                if expr.substring.length:
                    end_val = self.emit_expr(expr.substring.length, model_class=model_class)
                    if getattr(expr, "array_indices", None):
                        return f"{base_ref}[{s_idx}:{end_val}]"
                    return f"{base_ref}[{s_idx}:{s_idx} + {end_val}]"
                return f"{base_ref}[{s_idx}:]"
            return base_ref
        elif expr.op == "array_length":
            target = self.emit_expr(expr.items[0], model_class=model_class)
            return f"len({target})"
        elif expr.op == "func_call":
            if expr.symbol_id in ("len", "max", "min", "abs", "int", "str"):
                fn_name = expr.symbol_id
            else:
                fn_name = self.ctx.clean_func_name(expr.symbol_id or "func")
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
            return "loop_counter"
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
            lhs_sym = self.ctx.get_symbol(expr.lhs.symbol_id) if (expr.lhs and expr.lhs.symbol_id) else None
            if lhs_sym and lhs_sym.semantic_type.base == "date" and expr.op in ("add", "subtract"):
                lhs = self.emit_expr(expr.lhs, model_class=model_class)
                rhs_val = expr.rhs.value if expr.rhs else 1
                op = "+" if expr.op == "add" else "-"
                return f"({lhs} {op} timedelta(days={rhs_val}))"

            lhs = self.emit_expr(expr.lhs, model_class=model_class) if expr.lhs else ""
            rhs = self.emit_expr(expr.rhs, model_class=model_class) if expr.rhs else ""
            return f"({lhs} {op_map[expr.op]} {rhs})"
        return "None"
