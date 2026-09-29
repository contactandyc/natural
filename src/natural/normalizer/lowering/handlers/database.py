# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import List, Union
from natural.ir.models import (
    AcceptStatement,
    AtBreakStatement,
    AtEndOfDataStatement,
    AtStartOfDataStatement,
    BackoutTransactionStatement,
    DeleteStatement,
    EndTransactionStatement,
    FindStatement,
    GetSameStatement,
    GetStatement,
    HistogramStatement,
    ReadStatement,
    RejectStatement,
    StoreStatement,
    UpdateStatement,
)
from natural.ir.semantic import (
    AtBreakOp,
    AtEndOfDataOp,
    AtStartOfDataOp,
    BranchOp,
    ContinueOp,
    EntityDeleteOp,
    EntityGetOp,
    EntityRefreshOp,
    EntityStoreOp,
    EntityUpdateOp,
    QueryIterationOp,
    SemanticExpression,
    SemanticStatement,
    Symbol,
    TransactionOp,
)
from natural.normalizer.lowering.context import ActiveLoopContext, LoweringContext
from natural.normalizer.lowering.expressions import ExpressionLowerer


def _lower_find_or_read(
        stmt: Union[FindStatement, ReadStatement],
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    ctx.loop_counter += 1
    op_name = "find" if isinstance(stmt, FindStatement) else "read"
    loop_id = f"loop.{op_name}_{ctx.loop_counter:03d}"

    v_def = ctx.find_view_definition(stmt.view_name)
    if v_def and v_def.ddm_name:
        entity_name = v_def.ddm_name.replace("-VIEW", "")
    else:
        entity_name = stmt.view_name.replace("-VIEW", "")

    ctx.push_loop(
        ActiveLoopContext(loop_id=loop_id, label=stmt.label, entity=entity_name, view_name=stmt.view_name)
    )

    lookup_ddm_name = (v_def.ddm_name if v_def and v_def.ddm_name else stmt.view_name)
    if ctx.workspace:
        ddm = ctx.workspace.get_ddm(lookup_ddm_name)
        if ddm:
            for field in ddm.inline_fields:
                clean_name = field.name.lower()
                sym_id = f"sym.entity.{stmt.view_name.lower()}.{clean_name}"
                raw_spec = field.format.raw_spec if field.format else "A"
                is_arr = bool(field.array_dim or getattr(field, "is_periodic", False) or getattr(field, "is_multiple", False))
                ctx.symbols[field.name] = Symbol(
                    id=sym_id,
                    name=field.name,
                    scope="entity_field",
                    semantic_type=ctx.parse_format(raw_spec),
                    is_array=is_arr,
                )

    limit_val = getattr(stmt, "limit", None)
    cardinality = "one" if limit_val == 1 else "many"

    if isinstance(stmt, FindStatement):
        if getattr(stmt, "criteria", None):
            predicate = expr_lowerer.lower(stmt.criteria)
        elif stmt.descriptor and stmt.operand:
            predicate = SemanticExpression(
                op="eq",
                lhs=SemanticExpression(
                    op="entity_field",
                    symbol_id=f"sym.entity.{stmt.view_name.lower()}.{stmt.descriptor.lower()}",
                ),
                rhs=expr_lowerer.lower(stmt.operand),
            )
        else:
            predicate = SemanticExpression(op="literal", value=True)
        on_empty = dispatcher.lower_statements(stmt.on_empty)
    else:
        predicate = SemanticExpression(op="literal", value=True)
        desc = getattr(stmt, "by_descriptor", None)
        if desc and getattr(stmt, "starting_from", None):
            sym_field = f"sym.entity.{stmt.view_name.lower()}.{desc.lower()}"
            start_pred = SemanticExpression(
                op="gte",
                lhs=SemanticExpression(op="entity_field", symbol_id=sym_field),
                rhs=expr_lowerer.lower(stmt.starting_from),
            )
            if getattr(stmt, "thru_value", None):
                thru_pred = SemanticExpression(
                    op="lte",
                    lhs=SemanticExpression(op="entity_field", symbol_id=sym_field),
                    rhs=expr_lowerer.lower(stmt.thru_value),
                )
                predicate = SemanticExpression(op="and", lhs=start_pred, rhs=thru_pred)
            else:
                predicate = start_pred
        on_empty = []

    body_ops = dispatcher.lower_statements(stmt.body)
    ctx.pop_loop()

    op = QueryIterationOp(
        id=loop_id,
        label=stmt.label,
        entity=entity_name,
        natural_view=stmt.view_name,
        predicate=predicate,
        limit=limit_val,
        cardinality=cardinality,
        body=body_ops,
        on_empty=on_empty,
    )
    return [op]


def lower_find(
        stmt: FindStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    return _lower_find_or_read(stmt, ctx, expr_lowerer, dispatcher)


def lower_read(
        stmt: ReadStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    return _lower_find_or_read(stmt, ctx, expr_lowerer, dispatcher)


def lower_histogram(
        stmt: HistogramStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    ctx.loop_counter += 1
    loop_id = f"loop.histogram_{ctx.loop_counter:03d}"
    entity_name = stmt.view_name.replace("-VIEW", "")
    ctx.push_loop(
        ActiveLoopContext(
            loop_id=loop_id,
            label=stmt.label,
            entity=entity_name,
            view_name=stmt.view_name,
            is_histogram=True,
        )
    )

    if ctx.workspace:
        ddm = ctx.workspace.get_ddm(stmt.view_name)
        if ddm:
            for field in ddm.inline_fields:
                clean_name = field.name.lower()
                sym_id = f"sym.entity.{stmt.view_name.lower()}.{clean_name}"
                raw_spec = field.format.raw_spec if field.format else "A"
                is_arr = bool(field.array_dim or getattr(field, "is_periodic", False) or getattr(field, "is_multiple", False))
                ctx.symbols[field.name] = Symbol(
                    id=sym_id,
                    name=field.name,
                    scope="entity_field",
                    semantic_type=ctx.parse_format(raw_spec),
                    is_array=is_arr,
                )

    sym_field = f"sym.entity.{stmt.view_name.lower()}.{stmt.descriptor.lower()}"
    predicate = SemanticExpression(op="literal", value=True)
    if stmt.starting_from:
        start_pred = SemanticExpression(
            op="gte",
            lhs=SemanticExpression(op="entity_field", symbol_id=sym_field),
            rhs=expr_lowerer.lower(stmt.starting_from),
        )
        if stmt.thru_value:
            thru_pred = SemanticExpression(
                op="lte",
                lhs=SemanticExpression(op="entity_field", symbol_id=sym_field),
                rhs=expr_lowerer.lower(stmt.thru_value),
            )
            predicate = SemanticExpression(op="and", lhs=start_pred, rhs=thru_pred)
        else:
            predicate = start_pred

    body_ops = dispatcher.lower_statements(stmt.body)
    ctx.pop_loop()

    op = QueryIterationOp(
        id=loop_id,
        label=stmt.label,
        entity=entity_name,
        natural_view=stmt.view_name,
        predicate=predicate,
        limit=stmt.limit,
        cardinality="histogram",
        descriptor=stmt.descriptor,
        body=body_ops,
    )
    return [op]


def lower_get(
        stmt: GetStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    v_name = stmt.view_name.upper()
    v_def = ctx.find_view_definition(v_name)
    entity_name = (v_def.ddm_name if v_def and v_def.ddm_name else v_name).replace("-VIEW", "")
    target_var = f"{v_name.lower()}_record"
    key_expr = expr_lowerer.lower(stmt.arguments[0]) if stmt.arguments else SemanticExpression(op="ref", symbol_id="sym.entity.active.id")
    return [
        EntityGetOp(
            target_var=target_var,
            entity=entity_name,
            natural_view=v_name,
            key_expr=key_expr,
        )
    ]


def lower_get_same(
        stmt: GetSameStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    matched_entity = "active_record"
    for loop_ctx in reversed(ctx.loop_stack):
        if loop_ctx.entity:
            matched_entity = loop_ctx.entity
            break
    return [EntityRefreshOp(target_loop_id=ctx.resolve_target_loop(None), entity=matched_entity)]


def lower_update(
        stmt: UpdateStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    target_loop_id = ctx.resolve_target_loop(stmt.loop_label)
    matched_entity = "active_record"
    for loop_ctx in reversed(ctx.loop_stack):
        if loop_ctx.loop_id == target_loop_id and loop_ctx.entity:
            matched_entity = loop_ctx.entity
            break
    return [EntityUpdateOp(target_loop_id=target_loop_id, entity=matched_entity)]


def lower_delete(
        stmt: DeleteStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    target_loop_id = ctx.resolve_target_loop(stmt.loop_label)
    matched_entity = "active_record"
    for loop_ctx in reversed(ctx.loop_stack):
        if loop_ctx.loop_id == target_loop_id and loop_ctx.entity:
            matched_entity = loop_ctx.entity
            break
    return [EntityDeleteOp(target_loop_id=target_loop_id, entity=matched_entity)]


def lower_store(
        stmt: StoreStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    entity_name = stmt.view_name.replace("-VIEW", "")
    return [EntityStoreOp(entity=entity_name, natural_view=stmt.view_name)]


def lower_accept(
        stmt: AcceptStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    target_loop = ctx.resolve_target_loop(None)
    cond = expr_lowerer.lower(stmt.criteria)
    not_cond = SemanticExpression(op="not", lhs=cond)
    return [
        BranchOp(
            condition=not_cond,
            then_branch=[ContinueOp(target_loop_id=target_loop)],
        )
    ]


def lower_reject(
        stmt: RejectStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    target_loop = ctx.resolve_target_loop(None)
    cond = expr_lowerer.lower(stmt.criteria)
    return [
        BranchOp(
            condition=cond,
            then_branch=[ContinueOp(target_loop_id=target_loop)],
        )
    ]


def lower_end_transaction(
        stmt: EndTransactionStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    return [TransactionOp(action="commit")]


def lower_backout_transaction(
        stmt: BackoutTransactionStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    return [TransactionOp(action="rollback")]


def lower_at_start(
        stmt: AtStartOfDataStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    return [AtStartOfDataOp(body=dispatcher.lower_statements(stmt.body))]


def lower_at_end(
        stmt: AtEndOfDataStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    return [AtEndOfDataOp(body=dispatcher.lower_statements(stmt.body))]


def lower_at_break(
        stmt: AtBreakStatement,
        ctx: LoweringContext,
        expr_lowerer: ExpressionLowerer,
        dispatcher,
) -> List[SemanticStatement]:
    resolved_field = ""
    if stmt.field_name:
        resolved_field = ctx.resolve_ref(stmt.field_name)
    return [
        AtBreakOp(
            field_name=resolved_field,
            is_before=stmt.is_before,
            body=dispatcher.lower_statements(stmt.body),
        )
    ]
