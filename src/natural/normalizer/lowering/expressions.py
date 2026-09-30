# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import re
from decimal import Decimal
from typing import Optional
from natural.ir.models import Expression
from natural.ir.semantic import SemanticExpression, SemanticSubstring, SemanticType
from natural.normalizer.lowering.context import LoweringContext, normalize_fn_name


class ExpressionLowerer:
    """Transforms syntactic AST Expressions into typed Semantic DAG Expressions."""

    def __init__(self, ctx: LoweringContext):
        self.ctx = ctx

    def lower(self, expr: Expression) -> SemanticExpression:
        if expr.kind == "tab":
            return SemanticExpression(
                op="tab",
                value=expr.value,
                inferred_type=SemanticType(base="string"),
            )
        elif expr.kind == "newline":
            return SemanticExpression(
                op="newline",
                value=expr.value or "/",
                inferred_type=SemanticType(base="string"),
            )

        if expr.kind == "ref" and str(expr.value).startswith("*"):
            expr = Expression(kind="sys_var", value=expr.value)

        if expr.kind == "func_call":
            fn_name = expr.func_name or "unknown_func"
            lowered_args = [self.lower(arg) for arg in expr.func_args]

            # Infer function return type from AST declarations or built-ins
            ret_type = None
            fn_clean = normalize_fn_name(fn_name)
            for f_name, f_def in self.ctx.ast.functions.items():
                if normalize_fn_name(f_name) == fn_clean and f_def.returns_raw:
                    m = re.search(r"\(([^)]+)\)", f_def.returns_raw)
                    raw_ret = m.group(1) if m else f_def.returns_raw.replace("RETURNS", "").strip()
                    ret_type = self.ctx.parse_format(raw_ret)
                    break

            if not ret_type:
                if fn_name in ("len", "int", "abs"):
                    ret_type = SemanticType(base="integer", length=4)
                elif fn_name == "str":
                    ret_type = SemanticType(base="string")
                elif fn_name == "Decimal":
                    ret_type = SemanticType(base="decimal", precision=10, scale=2)
                else:
                    ret_type = SemanticType(base="unknown")

            return SemanticExpression(
                op="func_call",
                symbol_id=fn_name,
                items=lowered_args,
                inferred_type=ret_type,
            )

        if expr.kind == "ref":
            resolved_id = self.ctx.resolve_ref(str(expr.value))
            sub_op = None
            if expr.substring:
                sub_op = SemanticSubstring(
                    start=self.lower(expr.substring.start),
                    length=self.lower(expr.substring.length) if expr.substring.length else None,
                )
            arr_indices = [self.lower(idx) for idx in getattr(expr, "array_indices", [])]

            if sub_op:
                inf_type = SemanticType(base="string")
            else:
                sym = self.ctx.get_symbol(resolved_id) or self.ctx.get_symbol(str(expr.value))
                if sym and sym.redefine_parent:
                    # Redefined character slices are exposed as integer properties
                    if sym.semantic_type.base == "string":
                        inf_type = sym.semantic_type
                    else:
                        inf_type = SemanticType(
                            base="integer",
                            length=sym.semantic_type.length or sym.semantic_type.precision or 4,
                        )
                else:
                    inf_type = sym.semantic_type if sym else SemanticType(base="unknown")

            return SemanticExpression(
                op="ref",
                symbol_id=resolved_id,
                array_indices=arr_indices,
                substring=sub_op,
                inferred_type=inf_type,
            )

        elif expr.kind == "tuple":
            items = [self.lower(it) for it in expr.array_indices]
            return SemanticExpression(
                op="tuple",
                items=items,
                inferred_type=SemanticType(base="tuple"),
            )

        elif expr.kind == "literal":
            if isinstance(expr.value, bool):
                inf_type = SemanticType(base="boolean", length=1)
            elif isinstance(expr.value, Decimal):
                scale = abs(expr.value.as_tuple().exponent) if isinstance(expr.value.as_tuple().exponent, int) else 2
                inf_type = SemanticType(base="decimal", precision=10, scale=scale)
            elif isinstance(expr.value, int):
                inf_type = SemanticType(base="integer", length=4)
            elif isinstance(expr.value, str):
                inf_type = SemanticType(base="string", length=len(expr.value))
            else:
                inf_type = SemanticType(base="unknown")

            return SemanticExpression(
                op="literal",
                value=expr.value,
                inferred_type=inf_type,
            )

        elif expr.kind == "sys_var":
            var_name = str(expr.value).upper()
            if var_name.startswith("*OCC"):
                m = re.search(r"\*OCC\(\s*([*#\+A-Za-z0-9\-_\.]+)", var_name)
                if m:
                    arr_name = m.group(1).strip()
                    arr_id = self.ctx.resolve_ref(arr_name)
                    return SemanticExpression(
                        op="array_length",
                        items=[SemanticExpression(op="ref", symbol_id=arr_id)],
                        inferred_type=SemanticType(base="integer", length=4),
                    )
                return SemanticExpression(op="literal", value=0, inferred_type=SemanticType(base="integer", length=4))
            elif var_name.startswith("*COUNTER"):
                return SemanticExpression(op="counter", inferred_type=SemanticType(base="integer", length=4))
            elif var_name.startswith("*ISN"):
                return SemanticExpression(
                    op="ref",
                    symbol_id="sym.entity.active.id",
                    inferred_type=SemanticType(base="integer", length=4),
                )
            elif var_name.startswith("*NUMBER"):
                for loop_ctx in reversed(self.ctx.loop_stack):
                    if getattr(loop_ctx, "is_histogram", False):
                        return SemanticExpression(
                            op="ref",
                            symbol_id="record.number",
                            inferred_type=SemanticType(base="integer", length=4),
                        )
                return SemanticExpression(op="literal", value=1, inferred_type=SemanticType(base="integer", length=4))
            elif var_name in ("*DATX", "*DATN"):
                return SemanticExpression(op="sys_date", inferred_type=SemanticType(base="date", length=8))
            elif var_name == "*TIME":
                return SemanticExpression(op="sys_time", inferred_type=SemanticType(base="string", length=8))
            return SemanticExpression(op="literal", value=var_name, inferred_type=SemanticType(base="string"))

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
                                inferred_type=SemanticType(base="boolean", length=1),
                            )
                        )
                    res = pairs[0]
                    for p in pairs[1:]:
                        res = SemanticExpression(
                            op="and",
                            lhs=res,
                            rhs=p,
                            inferred_type=SemanticType(base="boolean", length=1),
                        )
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
                                        inferred_type=SemanticType(base="string", length=s_len),
                                    )
                                    sub_rhs = SemanticExpression(
                                        op="ref",
                                        symbol_id=self.ctx.resolve_ref(str(expr.right.value)),
                                        substring=SemanticSubstring(
                                            start=SemanticExpression(op="literal", value=curr_key_offset, inferred_type=SemanticType(base="integer", length=4)),
                                            length=SemanticExpression(op="literal", value=s_len, inferred_type=SemanticType(base="integer", length=4)),
                                        ),
                                        inferred_type=SemanticType(base="string", length=s_len),
                                    )
                                    curr_key_offset += s_len
                                    sub_pairs.append(SemanticExpression(op="eq", lhs=sub_lhs, rhs=sub_rhs, inferred_type=SemanticType(base="boolean", length=1)))
                                res = sub_pairs[0]
                                for sp in sub_pairs[1:]:
                                    res = SemanticExpression(op="and", lhs=res, rhs=sp, inferred_type=SemanticType(base="boolean", length=1))
                                return res

            lhs_sem = self.lower(expr.left) if expr.left else None
            rhs_sem = self.lower(expr.right) if expr.right else None
            op_str = expr.operator.upper() if expr.operator else ""

            # Infer binary operation result type
            if op_str in (">", "<", "=", ">=", "<=", "<>", "AND", "OR"):
                inf_type = SemanticType(base="boolean", length=1)
            elif lhs_sem and lhs_sem.inferred_type and lhs_sem.inferred_type.base == "date" and op_str in ("+", "-"):
                inf_type = SemanticType(base="date", length=8)
            elif op_str == "/":
                inf_type = SemanticType(base="decimal", precision=10, scale=2)
            elif (lhs_sem and lhs_sem.inferred_type and lhs_sem.inferred_type.base == "decimal") or (rhs_sem and rhs_sem.inferred_type and rhs_sem.inferred_type.base == "decimal"):
                inf_type = lhs_sem.inferred_type if (lhs_sem and lhs_sem.inferred_type and lhs_sem.inferred_type.base == "decimal") else rhs_sem.inferred_type
            elif (lhs_sem and lhs_sem.inferred_type and lhs_sem.inferred_type.base == "integer") and (rhs_sem and rhs_sem.inferred_type and rhs_sem.inferred_type.base == "integer"):
                inf_type = SemanticType(base="integer", length=4)
            else:
                inf_type = lhs_sem.inferred_type if (lhs_sem and lhs_sem.inferred_type) else SemanticType(base="unknown")

            return SemanticExpression(
                op=op_map.get(expr.operator, expr.operator.lower() if expr.operator else "unknown"),
                lhs=lhs_sem,
                rhs=rhs_sem,
                inferred_type=inf_type,
            )

        return SemanticExpression(op="unknown", inferred_type=SemanticType(base="unknown"))
