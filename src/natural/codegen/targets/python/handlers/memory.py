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
from natural.codegen.targets.python.formatters import convert_edit_mask, format_numeric_edit_mask


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
    source_sym = ctx.get_symbol(op.expr.symbol_id) if op.expr.symbol_id else None

    if op.target_substring:
        start_val = expr_emitter.emit_expr(op.target_substring.start)
        s_idx = f"({start_val} - 1)"
        rhs_val = f"str({expr_emitter.emit_expr(op.expr)})"
        if op.target_substring.length:
            len_val = expr_emitter.emit_expr(op.target_substring.length)
            e_idx = f"({s_idx} + {len_val})"
            ctx.emit_line(f"{target} = {target}[:{s_idx}] + {rhs_val} + {target}[{e_idx}:]")
        else:
            ctx.emit_line(f"{target} = {target}[:{s_idx}] + {rhs_val}")
        return

    if op.edit_mask and target_sym and source_sym:
        if target_sym.semantic_type.base == "string" and source_sym.semantic_type.base == "date":
            py_mask = convert_edit_mask(op.edit_mask)
            ctx.emit_line(f"{target} = {ctx.resolve_ref(op.expr.symbol_id)}.strftime('{py_mask}')")
            return
        elif target_sym.semantic_type.base == "date" and source_sym.semantic_type.base == "string":
            py_mask = convert_edit_mask(op.edit_mask)
            ctx.emit_line(f"{target} = datetime.strptime({ctx.resolve_ref(op.expr.symbol_id)}, '{py_mask}').date()")
            return
        elif target_sym.semantic_type.base == "string" and source_sym.semantic_type.base in ("decimal", "integer", "numeric"):
            src_ref = ctx.resolve_ref(op.expr.symbol_id)
            formatted_line = format_numeric_edit_mask(target, src_ref, op.edit_mask)
            ctx.emit_line(formatted_line)
            return
        elif target_sym.semantic_type.base in ("decimal", "numeric") and source_sym.semantic_type.base == "string":
            src_ref = ctx.resolve_ref(op.expr.symbol_id)
            ctx.emit_line(f"_val = {src_ref}.strip().replace('$', '').replace(',', '').replace(' ', '').replace('+', '')")
            ctx.emit_line(f"_is_neg = _val.endswith('-') or _val.startswith('-') or _val.endswith(('CR', 'DB')) or (_val.startswith('(') and _val.endswith(')'))")
            ctx.emit_line(f"_num = _val.rstrip('-CRDBcrdb').lstrip('-+(').rstrip(')').strip()")
            ctx.emit_line(f"{target} = -Decimal(_num) if _is_neg else (Decimal(_num) if _num else Decimal('0'))")
            return
        elif target_sym.semantic_type.base == "integer" and source_sym.semantic_type.base == "string":
            src_ref = ctx.resolve_ref(op.expr.symbol_id)
            ctx.emit_line(f"_val = {src_ref}.strip().replace('$', '').replace(',', '').replace(' ', '').replace('+', '')")
            ctx.emit_line(f"_is_neg = _val.endswith('-') or _val.startswith('-') or _val.endswith(('CR', 'DB')) or (_val.startswith('(') and _val.endswith(')'))")
            ctx.emit_line(f"_num = _val.rstrip('-CRDBcrdb').lstrip('-+(').rstrip(')').strip()")
            ctx.emit_line(f"{target} = -int(_num) if _is_neg else (int(_num) if _num else 0)")
            return

    if target_sym and target_sym.semantic_type.base in ("decimal", "numeric") and source_sym and source_sym.semantic_type.base == "string":
        src_ref = ctx.resolve_ref(op.expr.symbol_id)
        ctx.emit_line(f"_val = {src_ref}.strip().replace('$', '').replace(',', '').replace(' ', '').replace('+', '')")
        ctx.emit_line(f"_is_neg = _val.endswith('-') or _val.startswith('-') or _val.endswith(('CR', 'DB')) or (_val.startswith('(') and _val.endswith(')'))")
        ctx.emit_line(f"_num = _val.rstrip('-CRDBcrdb').lstrip('-+(').rstrip(')').strip()")
        ctx.emit_line(f"{target} = -Decimal(_num) if _is_neg else (Decimal(_num) if _num else Decimal('0'))")
        return

    expr = expr_emitter.emit_expr(op.expr)
    if op.rounded and target_sym and target_sym.semantic_type.base == "decimal":
        scale = target_sym.semantic_type.scale or 0
        quant = f"Decimal('1e-{scale}')" if scale > 0 else "Decimal('1')"
        ctx.emit_line(f"{target} = ({expr}).quantize({quant}, rounding=ROUND_HALF_UP)")
    elif op.rounded and target_sym and target_sym.semantic_type.base == "integer":
        ctx.emit_line(f"{target} = int(round({expr}))")
    elif target_sym and target_sym.semantic_type.base == "integer":
        if op.expr.op == "divide":
            ctx.emit_line(f"{target} = int({expr})")
        else:
            ctx.emit_line(f"{target} = {expr}")
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
        ctx.emit_line(f"_diff = max(0, int({size}) - len({target}))")
        ctx.emit_line(f"{target}.extend([None] * _diff)")
    elif op.action == "REDUCE":
        ctx.emit_line(f"del {target}[int({size}):]")
    else:
        ctx.emit_line(f"if int({size}) < len({target}):")
        with ctx.indent():
            ctx.emit_line(f"del {target}[int({size}):]")
        ctx.emit_line("else:")
        with ctx.indent():
            ctx.emit_line(f"_diff = max(0, int({size}) - len({target}))")
            ctx.emit_line(f"{target}.extend([None] * _diff)")
