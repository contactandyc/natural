# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import List
from natural.ir.models import CallnatStatement, FetchStatement, PerformStatement
from natural.ir.semantic import CallArgBinding, CallProgramOp, CallSubroutineOp, FetchOp, SemanticStatement
from natural.normalizer.lowering.context import LoweringContext
from natural.normalizer.lowering.expressions import ExpressionLowerer


def lower_perform(
        stmt: PerformStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    return [CallSubroutineOp(subroutine_name=stmt.subroutine_name)]


def lower_callnat(
        stmt: CallnatStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    param_exprs = [expr_lowerer.lower(p) for p in stmt.parameters]
    bindings: List[CallArgBinding] = []

    formal_params = []
    if ctx.workspace:
        formal_params = ctx.workspace.get_subprogram_parameters(stmt.subprogram_name)

    for idx, arg_stmt in enumerate(stmt.parameters):
        lowered_arg = param_exprs[idx]
        if idx < len(formal_params):
            callee_field_name = formal_params[idx].name.lower().replace("#", "")
        else:
            callee_field_name = f"arg_{idx + 1}"

        is_lval = (arg_stmt.kind == "ref")
        target_id = ctx.resolve_ref(str(arg_stmt.value)) if is_lval else None

        bindings.append(
            CallArgBinding(
                caller_expr=lowered_arg,
                callee_field=callee_field_name,
                is_lvalue=is_lval,
                caller_target_id=target_id,
            )
        )

    return [
        CallProgramOp(
            program_name=stmt.subprogram_name,
            parameters=param_exprs,
            bindings=bindings,
        )
    ]


def lower_fetch(
        stmt: FetchStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    param_exprs = [expr_lowerer.lower(p) for p in stmt.parameters]
    bindings: List[CallArgBinding] = []

    formal_params = []
    if ctx.workspace:
        formal_params = ctx.workspace.get_subprogram_parameters(stmt.program_name)

    for idx, arg_stmt in enumerate(stmt.parameters):
        lowered_arg = param_exprs[idx]
        if idx < len(formal_params):
            callee_field_name = formal_params[idx].name.lower().replace("#", "")
        else:
            callee_field_name = f"arg_{idx + 1}"

        is_lval = (arg_stmt.kind == "ref")
        target_id = ctx.resolve_ref(str(arg_stmt.value)) if is_lval else None

        bindings.append(
            CallArgBinding(
                caller_expr=lowered_arg,
                callee_field=callee_field_name,
                is_lvalue=is_lval,
                caller_target_id=target_id,
            )
        )

    return [
        FetchOp(
            program_name=stmt.program_name,
            returning=stmt.returning,
            parameters=param_exprs,
            bindings=bindings,
        )
    ]
