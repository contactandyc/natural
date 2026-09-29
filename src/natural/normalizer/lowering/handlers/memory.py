# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import List
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
    CompressOp,
    ExamineOp,
    MoveAllOp,
    ResetOp,
    ResizeArrayOp,
    ReturnOp,
    SemanticExpression,
    SemanticStatement,
    SemanticSubstring,
    SeparateOp,
)
from natural.normalizer.lowering.context import LoweringContext, normalize_fn_name
from natural.normalizer.lowering.expressions import ExpressionLowerer


def lower_assign(
        stmt: AssignStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    target_str = str(stmt.target.value) if hasattr(stmt.target, "value") else str(stmt.target)

    if ctx.active_function_name:
        if normalize_fn_name(target_str) == normalize_fn_name(ctx.active_function_name):
            return [ReturnOp(expr=expr_lowerer.lower(stmt.value))]

    target_id = ctx.resolve_ref(target_str)
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
            expr=expr_lowerer.lower(stmt.value),
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
            assign_ops.append(
                AssignOp(
                    target_id=tgt_sym_id,
                    expr=SemanticExpression(op="ref", symbol_id=src_sym_id),
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
            expr=expr_lowerer.lower(stmt.source),
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
