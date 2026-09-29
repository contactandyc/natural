# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from natural.ir.semantic import (
    AtBreakOp,
    AtEndOfDataOp,
    AtStartOfDataOp,
    EntityDeleteOp,
    EntityGetOp,
    EntityRefreshOp,
    EntityStoreOp,
    EntityUpdateOp,
    QueryIterationOp,
    TransactionOp,
)
from natural.codegen.python_emitter.context import EmitterContext
from natural.codegen.python_emitter.expressions import PythonExpressionEmitter


def emit_query_iteration(
        op: QueryIterationOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    model_name = ctx.clean_name(op.entity).title().replace("_", "")
    limit_clause = f".limit({op.limit})" if getattr(op, "limit", None) else ""

    old_loop_views = ctx.current_loop_views
    ctx.current_loop_views = [
        ctx.clean_name(op.natural_view),
        ctx.clean_name(op.entity),
    ]

    if getattr(op, "cardinality", "") == "histogram":
        col_name = ctx.clean_name(op.descriptor or "id")
        cond = expr_emitter.emit_expr(op.predicate, model_class=model_name)
        filter_clause = f".filter({cond})" if cond != "True" else ""
        ctx.emit_line(
            f"for loop_idx, record in enumerate(session.query({model_name}.{col_name}.label('{col_name}'), func.count({model_name}.{col_name}).label('number')){filter_clause}.group_by({model_name}.{col_name}){limit_clause}, 1):"
        )
        with ctx.indent():
            ctx.emit_line("loop_counter = loop_idx")
            if not op.body:
                ctx.emit_line("pass")
            for sub_op in op.body:
                dispatcher.emit_operation(sub_op)
        ctx.current_loop_views = old_loop_views
        return

    cond = expr_emitter.emit_expr(op.predicate, model_class=model_name)

    break_ops = [sub for sub in op.body if isinstance(sub, AtBreakOp) and sub.field_name]
    for b_op in break_ops:
        clean_f = ctx.clean_name(b_op.field_name)
        ctx.emit_line(f"_prev_{clean_f} = None")

    ctx.emit_line(f"for loop_idx, record in enumerate(session.query({model_name}).filter({cond}){limit_clause}, 1):")
    with ctx.indent():
        ctx.emit_line("loop_counter = loop_idx")
        if not op.body:
            ctx.emit_line("pass")
        for sub_op in op.body:
            dispatcher.emit_operation(sub_op)

        for b_op in break_ops:
            clean_f = ctx.clean_name(b_op.field_name)
            field_ref = ctx.resolve_ref(b_op.field_name)
            ctx.emit_line(f"_prev_{clean_f} = {field_ref}")

    ctx.current_loop_views = old_loop_views


def emit_entity_get(
        op: EntityGetOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    model_name = ctx.clean_name(op.entity).title().replace("_", "")
    target_var = ctx.clean_name(op.target_var)
    key_expr = expr_emitter.emit_expr(op.key_expr)
    ctx.emit_line(f"{target_var} = session.get({model_name}, {key_expr})")


def emit_entity_refresh(
        op: EntityRefreshOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    ctx.emit_line("session.refresh(record)")


def emit_entity_update(
        op: EntityUpdateOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    ctx.emit_line("session.flush()  # UPDATE committed for active loop")


def emit_entity_store(
        op: EntityStoreOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    model_name = ctx.clean_name(op.entity).title().replace("_", "")
    ctx.emit_line(f"new_record = {model_name}()")
    ctx.emit_line("session.add(new_record)")
    ctx.emit_line("session.flush()  # STORE committed")


def emit_entity_delete(
        op: EntityDeleteOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    ctx.emit_line("session.delete(record)")
    ctx.emit_line("session.flush()  # DELETE committed")


def emit_transaction(
        op: TransactionOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    if op.action == "commit":
        ctx.emit_line("session.commit()")
    else:
        ctx.emit_line("session.rollback()")


def emit_at_start(
        op: AtStartOfDataOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    ctx.emit_line("if loop_idx == 1:")
    with ctx.indent():
        if not op.body:
            ctx.emit_line("pass")
        for sub_op in op.body:
            dispatcher.emit_operation(sub_op)


def emit_at_end(
        op: AtEndOfDataOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    ctx.emit_line("if loop_counter > 0:")
    with ctx.indent():
        if not op.body:
            ctx.emit_line("pass")
        for sub_op in op.body:
            dispatcher.emit_operation(sub_op)


def emit_at_break(
        op: AtBreakOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    if op.field_name:
        field_ref = ctx.resolve_ref(op.field_name)
        clean_f = ctx.clean_name(op.field_name)
        ctx.emit_line(f"if _prev_{clean_f} is not None and {field_ref} != _prev_{clean_f}:")
        with ctx.indent():
            if not op.body:
                ctx.emit_line("pass")
            for sub_op in op.body:
                dispatcher.emit_operation(sub_op)
    else:
        for sub_op in op.body:
            dispatcher.emit_operation(sub_op)
