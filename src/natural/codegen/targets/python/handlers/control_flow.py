# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from natural.ir.semantic import (
    BranchOp,
    BreakOp,
    ContinueOp,
    ForLoopOp,
    LoopOp,
    ReturnOp,
    TerminateOp,
)
from natural.codegen.targets.python.context import EmitterContext
from natural.codegen.targets.python.expressions import PythonExpressionEmitter


def emit_branch(
        op: BranchOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    cond = expr_emitter.emit_expr(op.condition)
    ctx.emit_line(f"if {cond}:")
    with ctx.indent():
        if not op.then_branch:
            ctx.emit_line("pass")
        for sub_op in op.then_branch:
            dispatcher.emit_operation(sub_op)
    if op.else_branch:
        ctx.emit_line("else:")
        with ctx.indent():
            for sub_op in op.else_branch:
                dispatcher.emit_operation(sub_op)


def emit_loop(
        op: LoopOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    if op.loop_type in ("until", "until_post") and op.condition:
        cond = expr_emitter.emit_expr(op.condition)
        ctx.emit_line("while True:")
        with ctx.indent():
            if not op.body:
                ctx.emit_line("pass")
            for sub_op in op.body:
                dispatcher.emit_operation(sub_op)
            ctx.emit_line(f"if {cond}:")
            with ctx.indent():
                ctx.emit_line("break")
    elif op.loop_type == "while" and op.condition:
        cond = expr_emitter.emit_expr(op.condition)
        ctx.emit_line(f"while {cond}:")
        with ctx.indent():
            if not op.body:
                ctx.emit_line("pass")
            for sub_op in op.body:
                dispatcher.emit_operation(sub_op)
    else:
        ctx.emit_line("while True:")
        with ctx.indent():
            if not op.body:
                ctx.emit_line("pass")
            for sub_op in op.body:
                dispatcher.emit_operation(sub_op)


def emit_for_loop(
        op: ForLoopOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    var_target = ctx.resolve_ref(op.variable_id)
    start_val = expr_emitter.emit_expr(op.start)
    end_val = expr_emitter.emit_expr(op.end)
    step_val = expr_emitter.emit_expr(op.step)
    ctx.emit_line(f"for loop_val in range(int({start_val}), int({end_val}) + 1, int({step_val})):")
    with ctx.indent():
        ctx.emit_line(f"{var_target} = loop_val")
        if not op.body:
            ctx.emit_line("pass")
        for sub_op in op.body:
            dispatcher.emit_operation(sub_op)


def emit_break(
        op: BreakOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    ctx.emit_line("break")


def emit_continue(
        op: ContinueOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    ctx.emit_line("continue")


def emit_return(
        op: ReturnOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    if op.expr:
        ctx.emit_line(f"return {expr_emitter.emit_expr(op.expr)}")
    else:
        ctx.emit_line("return ctx")


def emit_terminate(
        op: TerminateOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    ctx.emit_line("sys.exit(0)")
