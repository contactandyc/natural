# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from natural.ir.semantic import (
    AssignOp,
    CompressOp,
    ExamineOp,
    MoveAllOp,
    ResetOp,
    ResizeArrayOp,
    SeparateOp,
)
from natural.codegen.targets.python.context import EmitterContext
from natural.codegen.targets.python.expressions import PythonExpressionEmitter


def emit_assign(
        op: AssignOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    target = ctx.resolve_ref(op.target_id)
    if getattr(op, "target_indices", None):
        for idx in op.target_indices:
            if idx.op == "literal" and isinstance(idx.value, int):
                target = f"{target}[{idx.value - 1}]"
            else:
                idx_val = expr_emitter.emit_expr(idx)
                target = f"{target}[({idx_val} - 1)]"

    target_sym = ctx.get_symbol(op.target_id)

    if op.target_substring:
        start_val = expr_emitter.emit_expr(op.target_substring.start)
        rhs_val = expr_emitter.emit_expr(op.expr)
        if op.target_substring.length:
            len_val = expr_emitter.emit_expr(op.target_substring.length)
            ctx.emit_line(f"{target} = slice_assign({target}, {start_val}, {len_val}, {rhs_val})")
        else:
            ctx.emit_line(f"{target} = slice_assign({target}, {start_val}, None, {rhs_val})")
        return

    expr = expr_emitter.emit_expr(op.expr)
    if op.rounded and target_sym and target_sym.semantic_type.base == "decimal":
        scale = target_sym.semantic_type.scale or 0
        quant = f"Decimal('1e-{scale}')" if scale > 0 else "Decimal('1')"
        ctx.emit_line(f"{target} = ({expr}).quantize({quant}, rounding=ROUND_HALF_UP)")
    elif op.rounded and target_sym and target_sym.semantic_type.base == "integer":
        ctx.emit_line(f"{target} = int(round({expr}))")
    else:
        ctx.emit_line(f"{target} = {expr}")


def emit_move_all(
        op: MoveAllOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    target = ctx.resolve_ref(op.target_id)
    sym = ctx.get_symbol(op.target_id)
    length = sym.semantic_type.length if sym and sym.semantic_type.length else f"len({target})"
    fill = expr_emitter.emit_expr(op.fill_char)
    ctx.emit_line(f"{target} = str({fill}) * {length}")


def emit_compress(
        op: CompressOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    target = ctx.resolve_ref(op.target_id)
    if op.leaving_no_space:
        sep = "''"
    elif op.delimiter:
        sep = f"{expr_emitter.emit_expr(op.delimiter)}"
    else:
        sep = "' '"
    items_str = ", ".join(f"str({expr_emitter.emit_expr(e)})" for e in op.operands)
    ctx.emit_line(f"{target} = {sep}.join([{items_str}])")


def emit_separate(
        op: SeparateOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    source = expr_emitter.emit_expr(op.source)
    delimiter_code = f"str({expr_emitter.emit_expr(op.delimiter)})" if op.delimiter else "None"
    maxsplit = len(op.target_ids) - 1 if op.ignore_remainder else -1
    ctx.emit_line(f"_parts = {source}.split({delimiter_code}, {maxsplit})")
    for idx, target_id in enumerate(op.target_ids):
        target_var = ctx.resolve_ref(target_id)
        ctx.emit_line(f"{target_var} = _parts[{idx}] if len(_parts) > {idx} else ''")


def emit_examine(
        op: ExamineOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    target = ctx.resolve_ref(op.target_id)
    if op.translate_case == "UPPER":
        ctx.emit_line(f"{target} = {target}.upper()")
    elif op.translate_case == "LOWER":
        ctx.emit_line(f"{target} = {target}.lower()")
    elif op.replace_with:
        pattern = expr_emitter.emit_expr(op.pattern)
        rep = expr_emitter.emit_expr(op.replace_with)
        ctx.emit_line(f"{target} = {target}.replace(str({pattern}), str({rep}))")
    elif op.giving_number_id:
        pattern = expr_emitter.emit_expr(op.pattern)
        count_var = ctx.resolve_ref(op.giving_number_id)
        ctx.emit_line(f"{count_var} = {target}.count(str({pattern}))")


def emit_reset(
        op: ResetOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    target = ctx.resolve_ref(op.target_id)
    sym = ctx.get_symbol(op.target_id)
    if sym and sym.semantic_type.base == "decimal":
        default = "Decimal('0')"
    elif sym and sym.semantic_type.base == "integer":
        default = "0"
    elif sym and sym.semantic_type.base == "boolean":
        default = "False"
    else:
        default = '""'
    ctx.emit_line(f"{target} = {default}")


def emit_resize_array(
        op: ResizeArrayOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    target = ctx.resolve_ref(op.target_id)
    size = expr_emitter.emit_expr(op.size)
    if op.action == "EXPAND":
        ctx.emit_line(f"expand_array({target}, {size})")
    elif op.action == "REDUCE":
        ctx.emit_line(f"reduce_array({target}, {size})")
    else:
        ctx.emit_line(f"resize_array({target}, {size})")
