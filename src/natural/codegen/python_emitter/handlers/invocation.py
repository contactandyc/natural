# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from natural.ir.semantic import (
    CallProgramOp,
    CallSubroutineOp,
    FetchOp,
)
from natural.codegen.python_emitter.context import EmitterContext
from natural.codegen.python_emitter.expressions import PythonExpressionEmitter


def emit_call_subroutine(
        op: CallSubroutineOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    clean_sub = ctx.clean_name(op.subroutine_name)
    ctx.emit_line(f"sub_{clean_sub}(ctx, session)")


def emit_call_program(
        op: CallProgramOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    prog_clean = ctx.clean_name(op.program_name)
    sub_ctx_class = ctx.to_pascal_case(op.program_name) + "Context"
    sub_ctx_var = f"_{prog_clean}_ctx"

    ctx.emit_line(f"{sub_ctx_var} = {sub_ctx_class}()")
    for b in op.bindings:
        val_expr = expr_emitter.emit_expr(b.caller_expr)
        callee_prop = ctx.clean_name(b.callee_field)
        ctx.emit_line(f"{sub_ctx_var}.{callee_prop} = {val_expr}")

    ctx.emit_line(f"execute_{prog_clean}({sub_ctx_var}, session)")

    for b in op.bindings:
        if b.is_lvalue and b.caller_target_id:
            caller_var = ctx.resolve_ref(b.caller_target_id)
            callee_prop = ctx.clean_name(b.callee_field)
            ctx.emit_line(f"{caller_var} = {sub_ctx_var}.{callee_prop}")


def emit_fetch(
        op: FetchOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    prog_clean = ctx.clean_name(op.program_name)
    sub_ctx_class = ctx.to_pascal_case(op.program_name) + "Context"
    sub_ctx_var = f"_{prog_clean}_ctx"

    ctx.emit_line(f"{sub_ctx_var} = {sub_ctx_class}()")
    for b in op.bindings:
        val_expr = expr_emitter.emit_expr(b.caller_expr)
        callee_prop = ctx.clean_name(b.callee_field)
        ctx.emit_line(f"{sub_ctx_var}.{callee_prop} = {val_expr}")

    ctx.emit_line(f"execute_{prog_clean}({sub_ctx_var}, session)")

    for b in op.bindings:
        if b.is_lvalue and b.caller_target_id:
            caller_var = ctx.resolve_ref(b.caller_target_id)
            callee_prop = ctx.clean_name(b.callee_field)
            ctx.emit_line(f"{caller_var} = {sub_ctx_var}.{callee_prop}")

    if not op.returning:
        ctx.emit_line("return ctx")
