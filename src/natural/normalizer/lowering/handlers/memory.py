# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import re
from typing import List, Optional
from natural.ir.models import (
    AssignStatement,
    CompressStatement,
    ExamineStatement,
    Expression,
    MoveByNameStatement,
    MoveStatement,
    ResetStatement,
    ResizeArrayStatement,
    SeparateStatement,
)
from natural.ir.semantic import (
    AssignOp,
    CastKind,
    CompressOp,
    ExamineOp,
    MoveAllOp,
    ResetOp,
    ResizeArrayOp,
    ReturnOp,
    SemanticExpression,
    SemanticStatement,
    SemanticSubstring,
    SemanticType,
    SeparateOp,
    wrap_cast,
)
from natural.normalizer.lowering.context import LoweringContext, normalize_fn_name
from natural.normalizer.lowering.expressions import ExpressionLowerer


def coerce_type(
        expr: SemanticExpression,
        target_type: Optional[SemanticType],
        edit_mask: Optional[str] = None,
        rounded: bool = False,
) -> SemanticExpression:
    """Injects explicit wrap_cast nodes into expression DAG when types or representations differ."""
    if not target_type or not expr.inferred_type:
        if edit_mask:
            return wrap_cast(expr, target_type or SemanticType(base="string"), CastKind.EDIT_MASK, edit_mask=edit_mask)
        return expr

    source_type = expr.inferred_type

    # 1. Edit mask conversion (date formatting, date parsing, numeric masks)
    if edit_mask:
        if source_type.base == "date" and target_type.base == "string":
            return wrap_cast(expr, target_type, CastKind.FORMAT_DATE, edit_mask=edit_mask)
        elif source_type.base == "string" and target_type.base == "date":
            return wrap_cast(expr, target_type, CastKind.PARSE_DATE, edit_mask=edit_mask)
        elif source_type.base in ("decimal", "integer", "numeric") and target_type.base == "string":
            return wrap_cast(expr, target_type, CastKind.EDIT_MASK, edit_mask=edit_mask)
        elif target_type.base in ("decimal", "numeric") and source_type.base == "string":
            return wrap_cast(expr, target_type, CastKind.UNMASK, edit_mask=edit_mask)
        elif target_type.base == "integer" and source_type.base == "string":
            return wrap_cast(expr, target_type, CastKind.UNMASK, edit_mask=edit_mask)

    # 2. String to Numeric Unmasking
    if target_type.base in ("decimal", "numeric") and source_type.base == "string":
        return wrap_cast(expr, target_type, CastKind.UNMASK)
    if target_type.base == "integer" and source_type.base == "string":
        return wrap_cast(expr, target_type, CastKind.UNMASK)

    # 3. Numeric narrowing / division truncation
    if target_type.base == "integer" and (source_type.base in ("decimal", "numeric") or expr.op == "divide"):
        if (source_type.scale or 0) > 0 or expr.op == "divide":
            return wrap_cast(expr, target_type, CastKind.NARROW)

    # 4. Numeric widening (integer -> decimal)
    if target_type.base in ("decimal", "numeric") and source_type.base == "integer":
        return wrap_cast(expr, target_type, CastKind.WIDEN)

    # 5. Stringification
    if target_type.base == "string" and source_type.base not in ("string", "unknown"):
        return wrap_cast(expr, target_type, CastKind.STRINGIFY)

    return expr


def lower_assign(
        stmt: AssignStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    target_str = str(stmt.target.value) if hasattr(stmt.target, "value") else str(stmt.target)

    # Function return value assignment
    if ctx.active_function_name:
        if normalize_fn_name(target_str) == normalize_fn_name(ctx.active_function_name):
            val_expr = expr_lowerer.lower(stmt.value)
            fn_clean = normalize_fn_name(ctx.active_function_name)
            for f_name, f_def in ctx.ast.functions.items():
                if normalize_fn_name(f_name) == fn_clean and f_def.returns_raw:
                    m = re.search(r"\(([^)]+)\)", f_def.returns_raw)
                    raw_ret = m.group(1) if m else f_def.returns_raw.replace("RETURNS", "").strip()
                    ret_type = ctx.parse_format(raw_ret)
                    val_expr = coerce_type(val_expr, ret_type, edit_mask=None, rounded=stmt.rounded)
                    break
            return [ReturnOp(expr=val_expr)]

    target_id = ctx.resolve_ref(target_str)
    target_sym = ctx.get_symbol(target_id) or ctx.get_symbol(target_str)

    if target_sym and target_sym.redefine_parent:
        if target_sym.semantic_type.base == "string":
            target_type = target_sym.semantic_type
        else:
            target_type = SemanticType(
                base="integer",
                length=target_sym.semantic_type.length or target_sym.semantic_type.precision or 4,
            )
    else:
        target_type = target_sym.semantic_type if target_sym else None

    raw_expr = expr_lowerer.lower(stmt.value)
    coerced_expr = coerce_type(raw_expr, target_type, edit_mask=None, rounded=stmt.rounded)

    target_sub = None
    if hasattr(stmt.target, "substring") and stmt.target.substring:
        target_sub = SemanticSubstring(
            start=expr_lowerer.lower(stmt.target.substring.start),
            length=expr_lowerer.lower(stmt.target.substring.length) if stmt.target.substring.length else None,
        )
    target_indices = [expr_lowerer.lower(idx) for idx in getattr(stmt.target, "array_indices", [])]
    return [
        AssignOp(
            target_id=target_id,
            target_substring=target_sub,
            target_indices=target_indices,
            expr=coerced_expr,
            rounded=stmt.rounded,
        )
    ]


def lower_move_by_name(
        stmt: MoveByNameStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    source_fields = ctx.get_fields_for_scope(stmt.source)
    target_fields = ctx.get_fields_for_scope(stmt.target)

    target_map = {norm: (sym_id, orig_name) for norm, sym_id, orig_name in target_fields}
    assign_ops = []

    for norm, src_sym_id, _ in source_fields:
        if norm in target_map:
            tgt_sym_id, _ = target_map[norm]
            tgt_sym = ctx.get_symbol(tgt_sym_id)
            ref_expr = SemanticExpression(op="ref", symbol_id=src_sym_id)
            if tgt_sym:
                if tgt_sym.redefine_parent:
                    if tgt_sym.semantic_type.base == "string":
                        tgt_type = tgt_sym.semantic_type
                    else:
                        tgt_type = SemanticType(
                            base="integer",
                            length=tgt_sym.semantic_type.length or tgt_sym.semantic_type.precision or 4,
                        )
                else:
                    tgt_type = tgt_sym.semantic_type

                src_sym = ctx.get_symbol(src_sym_id)
                ref_expr.inferred_type = src_sym.semantic_type if src_sym else None
                ref_expr = coerce_type(ref_expr, tgt_type)
            assign_ops.append(
                AssignOp(
                    target_id=tgt_sym_id,
                    expr=ref_expr,
                )
            )

    return assign_ops


def lower_move(
        stmt: MoveStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    target_str = str(stmt.target.value) if hasattr(stmt.target, "value") else str(stmt.target)
    target_id = ctx.resolve_ref(target_str)
    target_sym = ctx.get_symbol(target_id) or ctx.get_symbol(target_str)

    if target_sym and target_sym.redefine_parent:
        if target_sym.semantic_type.base == "string":
            target_type = target_sym.semantic_type
        else:
            target_type = SemanticType(
                base="integer",
                length=target_sym.semantic_type.length or target_sym.semantic_type.precision or 4,
            )
    else:
        target_type = target_sym.semantic_type if target_sym else None

    raw_expr = expr_lowerer.lower(stmt.source)
    coerced_expr = coerce_type(raw_expr, target_type, edit_mask=stmt.edit_mask, rounded=False)

    target_sub = None
    if hasattr(stmt.target, "substring") and stmt.target.substring:
        target_sub = SemanticSubstring(
            start=expr_lowerer.lower(stmt.target.substring.start),
            length=expr_lowerer.lower(stmt.target.substring.length) if stmt.target.substring.length else None,
        )
    target_indices = [expr_lowerer.lower(idx) for idx in getattr(stmt.target, "array_indices", [])]

    if stmt.is_move_all:
        return [
            MoveAllOp(
                target_id=target_id,
                fill_char=expr_lowerer.lower(stmt.source),
            )
        ]

    return [
        AssignOp(
            target_id=target_id,
            target_substring=target_sub,
            target_indices=target_indices,
            expr=coerced_expr,
            edit_mask=stmt.edit_mask,
        )
    ]


def lower_compress(
        stmt: CompressStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    target_str = str(stmt.target.value) if hasattr(stmt.target, "value") else str(stmt.target)
    return [
        CompressOp(
            target_id=ctx.resolve_ref(target_str),
            operands=[expr_lowerer.lower(op) for op in stmt.operands],
            delimiter=expr_lowerer.lower(stmt.delimiter) if stmt.delimiter else None,
            with_delimiters=stmt.with_delimiters,
            leaving_no_space=stmt.leaving_no_space,
        )
    ]


def lower_separate(
        stmt: SeparateStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    return [
        SeparateOp(
            source=expr_lowerer.lower(stmt.source),
            target_ids=[ctx.resolve_ref(str(t.value)) for t in stmt.targets],
            delimiter=expr_lowerer.lower(stmt.delimiter) if stmt.delimiter else None,
            ignore_remainder=stmt.ignore_remainder,
        )
    ]


def lower_examine(
        stmt: ExamineStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    target_str = str(stmt.target.value) if hasattr(stmt.target, "value") else str(stmt.target)
    giving_id = ctx.resolve_ref(str(stmt.giving_number.value)) if stmt.giving_number else None
    return [
        ExamineOp(
            target_id=ctx.resolve_ref(target_str),
            pattern=expr_lowerer.lower(stmt.pattern) if stmt.pattern else None,
            replace_with=expr_lowerer.lower(stmt.replace_with) if stmt.replace_with else None,
            giving_number_id=giving_id,
            translate_case=stmt.translate_case,
        )
    ]


def lower_reset(
        stmt: ResetStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    ops = []
    for t in stmt.targets:
        target_str = str(t.value) if hasattr(t, "value") else str(t)
        ops.append(ResetOp(target_id=ctx.resolve_ref(target_str), initial=stmt.initial))
    return ops


def lower_resize_array(
        stmt: ResizeArrayStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    target_id = ctx.resolve_ref(stmt.array_name)
    size_op = expr_lowerer.lower(stmt.dimensions[0]) if stmt.dimensions else SemanticExpression(op="literal", value=0)
    return [ResizeArrayOp(target_id=target_id, action=stmt.action, size=size_op)]
