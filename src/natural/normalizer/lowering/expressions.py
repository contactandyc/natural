# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import re
from typing import Optional
from natural.ir.models import Expression
from natural.ir.semantic import SemanticExpression, SemanticSubstring
from natural.normalizer.lowering.context import LoweringContext


class ExpressionLowerer:
    """Transforms syntactic AST Expressions into Semantic DAG Expressions."""

    def __init__(self, ctx: LoweringContext):
        self.ctx = ctx

    def lower(self, expr: Expression) -> SemanticExpression:
        if expr.kind == "tab":
            return SemanticExpression(op="tab", value=expr.value)
        elif expr.kind == "newline":
            return SemanticExpression(op="newline", value=expr.value or "/")

        if expr.kind == "ref" and str(expr.value).startswith("*"):
            expr = Expression(kind="sys_var", value=expr.value)

        if expr.kind == "func_call":
            fn_name = expr.func_name or "unknown_func"
            lowered_args = [self.lower(arg) for arg in expr.func_args]
            return SemanticExpression(
                op="func_call",
                symbol_id=fn_name,
                items=lowered_args,
            )

        if expr.kind == "ref":
            sub_op = None
            if expr.substring:
                sub_op = SemanticSubstring(
                    start=self.lower(expr.substring.start),
                    length=self.lower(expr.substring.length) if expr.substring.length else None,
                )
            arr_indices = [self.lower(idx) for idx in getattr(expr, "array_indices", [])]
            return SemanticExpression(
                op="ref",
                symbol_id=self.ctx.resolve_ref(str(expr.value)),
                array_indices=arr_indices,
                substring=sub_op,
            )
        elif expr.kind == "tuple":
            items = [self.lower(it) for it in expr.array_indices]
            return SemanticExpression(op="tuple", items=items)
        elif expr.kind == "literal":
            return SemanticExpression(op="literal", value=expr.value)
        elif expr.kind == "sys_var":
            var_name = str(expr.value).upper()
            if var_name.startswith("*OCC"):
                m = re.search(r"\*OCC\(\s*([*#\+A-Za-z0-9\-_\.]+)", var_name)
                if m:
                    arr_name = m.group(1).strip()
                    arr_id = self.ctx.resolve_ref(arr_name)
                    return SemanticExpression(
                        op="func_call",
                        symbol_id="len",
                        items=[SemanticExpression(op="ref", symbol_id=arr_id)],
                    )
                return SemanticExpression(op="literal", value=0)
            elif var_name.startswith("*COUNTER"):
                return SemanticExpression(op="counter", value="loop_counter")
            elif var_name.startswith("*ISN"):
                return SemanticExpression(op="ref", symbol_id="sym.entity.active.id")
            elif var_name.startswith("*NUMBER"):
                for loop_ctx in reversed(self.ctx.loop_stack):
                    if getattr(loop_ctx, "is_histogram", False):
                        return SemanticExpression(op="ref", symbol_id="record.number")
                return SemanticExpression(op="literal", value=1)
            elif var_name in ("*DATX", "*DATN"):
                return SemanticExpression(op="sys_date", value="date.today()")
            elif var_name == "*TIME":
                return SemanticExpression(op="sys_time", value="datetime.now().time()")
            return SemanticExpression(op="literal", value=var_name)
        elif expr.kind == "binary_op":
            op_map = {
                "*": "multiply", "+": "add", "-": "subtract", "/": "divide",
                "%": "modulo", "MOD": "modulo",
                "**": "power", "^": "power",
                ">": "gt", "<": "lt", "=": "eq", ">=": "gte", "<=": "lte", "<>": "neq",
                "AND": "and", "OR": "or",
            }

            if expr.operator == "=" and expr.left and expr.right:
                if expr.left.kind == "tuple" and expr.right.kind == "tuple":
                    pairs = []
                    for l_item, r_item in zip(expr.left.array_indices, expr.right.array_indices):
                        pairs.append(
                            SemanticExpression(
                                op="eq",
                                lhs=self.lower(l_item),
                                rhs=self.lower(r_item),
                            )
                        )
                    res = pairs[0]
                    for p in pairs[1:]:
                        res = SemanticExpression(op="and", lhs=res, rhs=p)
                    return res

                if expr.left.kind == "ref" and self.ctx.loop_stack:
                    active_ctx = self.ctx.loop_stack[-1]
                    if active_ctx.view_name and self.ctx.workspace:
                        ddm = self.ctx.workspace.get_ddm(active_ctx.view_name)
                        if ddm:
                            f_match = next((f for f in ddm.inline_fields if f.name.upper() == str(expr.left.value).upper()), None)
                            if f_match and f_match.sub_fields:
                                sub_pairs = []
                                curr_key_offset = 1
                                for s_name, s_start, s_end in f_match.sub_fields:
                                    s_len = (s_end - s_start) + 1
                                    sub_lhs = SemanticExpression(
                                        op="entity_field",
                                        symbol_id=f"sym.entity.{active_ctx.view_name.lower()}.{s_name.lower()}",
                                    )
                                    sub_rhs = SemanticExpression(
                                        op="ref",
                                        symbol_id=self.ctx.resolve_ref(str(expr.right.value)),
                                        substring=SemanticSubstring(
                                            start=SemanticExpression(op="literal", value=curr_key_offset),
                                            length=SemanticExpression(op="literal", value=s_len),
                                        ),
                                    )
                                    curr_key_offset += s_len
                                    sub_pairs.append(SemanticExpression(op="eq", lhs=sub_lhs, rhs=sub_rhs))
                                res = sub_pairs[0]
                                for sp in sub_pairs[1:]:
                                    res = SemanticExpression(op="and", lhs=res, rhs=sp)
                                return res

            return SemanticExpression(
                op=op_map.get(expr.operator, expr.operator.lower() if expr.operator else "unknown"),
                lhs=self.lower(expr.left) if expr.left else None,
                rhs=self.lower(expr.right) if expr.right else None,
            )
        return SemanticExpression(op="unknown")
