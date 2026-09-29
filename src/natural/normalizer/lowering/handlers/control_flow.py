# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import List, Union
from natural.ir.models import (
    ConditionalStatement,
    DecideStatement,
    EscapeStatement,
    ForStatement,
    LoopStatement,
    OnErrorBlockStatement,
    StopStatement,
    TerminateStatement,
)
from natural.ir.semantic import (
    BranchOp,
    BreakOp,
    ContinueOp,
    ForLoopOp,
    LoopOp,
    OnErrorOp,
    ReturnOp,
    SemanticExpression,
    SemanticStatement,
    TerminateOp,
)
from natural.normalizer.lowering.context import ActiveLoopContext, LoweringContext
from natural.normalizer.lowering.expressions import ExpressionLowerer


def lower_conditional(
        stmt: ConditionalStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    return [
        BranchOp(
            condition=expr_lowerer.lower(stmt.condition),
            then_branch=dispatcher.lower_statements(stmt.then_branch),
            else_branch=dispatcher.lower_statements(stmt.else_branch),
        )
    ]


def lower_decide(
        stmt: DecideStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    if not stmt.branches:
        return dispatcher.lower_statements(stmt.none_branch)

    root_branch = None
    current_branch = None
    operand_expr = expr_lowerer.lower(stmt.operand) if stmt.operand else None

    for branch in stmt.branches:
        if stmt.decide_type == "ON" and operand_expr:
            condition = SemanticExpression(
                op="eq",
                lhs=operand_expr,
                rhs=expr_lowerer.lower(branch.value),
            )
        else:
            condition = expr_lowerer.lower(branch.value)

        new_branch = BranchOp(
            condition=condition,
            then_branch=dispatcher.lower_statements(branch.statements),
            else_branch=[],
        )

        if not root_branch:
            root_branch = new_branch
            current_branch = new_branch
        else:
            current_branch.else_branch = [new_branch]
            current_branch = new_branch

    if stmt.none_branch and current_branch:
        current_branch.else_branch = dispatcher.lower_statements(stmt.none_branch)

    return [root_branch] if root_branch else []


def lower_loop(
        stmt: LoopStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    ctx.loop_counter += 1
    loop_id = f"loop.repeat_{ctx.loop_counter:03d}"
    ctx.push_loop(ActiveLoopContext(loop_id=loop_id, label=stmt.label))

    cond = expr_lowerer.lower(stmt.condition) if stmt.condition else None
    body_ops = dispatcher.lower_statements(stmt.body)

    ctx.pop_loop()
    l_type = stmt.loop_type.lower() if hasattr(stmt, "loop_type") else ("until" if cond else "infinite")
    return [
        LoopOp(
            id=loop_id,
            label=stmt.label,
            loop_type=l_type,
            condition=cond,
            body=body_ops,
        )
    ]


def lower_for(
        stmt: ForStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    ctx.loop_counter += 1
    loop_id = f"loop.for_{ctx.loop_counter:03d}"
    ctx.push_loop(ActiveLoopContext(loop_id=loop_id, label=stmt.label))

    step_op = expr_lowerer.lower(stmt.step_expr) if stmt.step_expr else SemanticExpression(op="literal", value=1)
    body_ops = dispatcher.lower_statements(stmt.body)

    ctx.pop_loop()
    return [
        ForLoopOp(
            id=loop_id,
            label=stmt.label,
            variable_id=ctx.resolve_ref(stmt.variable),
            start=expr_lowerer.lower(stmt.start_expr),
            end=expr_lowerer.lower(stmt.end_expr),
            step=step_op,
            body=body_ops,
        )
    ]


def lower_escape(
        stmt: EscapeStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    if stmt.target == "ROUTINE":
        return [ReturnOp()]

    target_id = ctx.resolve_target_loop(stmt.loop_label)
    if stmt.target == "BOTTOM":
        return [BreakOp(target_loop_id=target_id)]
    elif stmt.target == "TOP":
        return [ContinueOp(target_loop_id=target_id)]
    return []


def lower_terminate(
        stmt: Union[StopStatement, TerminateStatement],
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    return [TerminateOp(exit_code=0)]


def lower_on_error(
        stmt: OnErrorBlockStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    return [OnErrorOp(body=dispatcher.lower_statements(stmt.body))]
