# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import List, Union
from natural.ir.models import (
    CloseWorkFileStatement,
    Expression,
    PrintStatement,
    ReadWorkFileStatement,
    WriteStatement,
    WriteWorkFileStatement,
)
from natural.ir.semantic import (
    CloseWorkFileOp,
    ReadWorkFileOp,
    SemanticExpression,
    SemanticStatement,
    WriteOp,
    WriteWorkFileOp,
)
from natural.normalizer.lowering.context import ActiveLoopContext, LoweringContext
from natural.normalizer.lowering.expressions import ExpressionLowerer


def lower_io_write(
        stmt: Union[WriteStatement, PrintStatement],
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    raw_items = stmt.items if isinstance(stmt, WriteStatement) else stmt.fields
    lowered_operands = []
    for it in raw_items:
        if isinstance(it, Expression):
            lowered_operands.append(expr_lowerer.lower(it))
        else:
            lowered_operands.append(SemanticExpression(op="literal", value=it))
    return [
        WriteOp(
            operands=lowered_operands,
            is_write=isinstance(stmt, WriteStatement),
        )
    ]


def lower_write_work_file(
        stmt: WriteWorkFileStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    return [
        WriteWorkFileOp(
            file_number=stmt.file_number,
            operands=[expr_lowerer.lower(f) for f in stmt.fields],
        )
    ]


def lower_close_work_file(
        stmt: CloseWorkFileStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    return [CloseWorkFileOp(file_number=stmt.file_number)]


def lower_read_work_file(
        stmt: ReadWorkFileStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    ctx.loop_counter += 1
    loop_id = f"loop.workfile_{ctx.loop_counter:03d}"
    ctx.push_loop(ActiveLoopContext(loop_id=loop_id, label=stmt.label))

    targets = [ctx.resolve_ref(str(f.value)) for f in stmt.fields]
    body_ops = dispatcher.lower_statements(stmt.body)

    ctx.pop_loop()
    return [
        ReadWorkFileOp(
            id=loop_id,
            label=stmt.label,
            file_number=stmt.file_number,
            target_ids=targets,
            body=body_ops,
        )
    ]
