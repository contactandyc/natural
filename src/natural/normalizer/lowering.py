# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import List, Dict, Optional
from natural.ir.models import (
    NaturalModule,
    AssignStatement,
    FindStatement,
    ReadStatement,
    ConditionalStatement,
    DecideStatement,
    EscapeStatement,
    Expression,
    LoopStatement,
    ForStatement,
    MoveStatement,
    CompressStatement,
    ExamineStatement,
    ResetStatement,
    PerformStatement,
    UpdateStatement,
    DeleteStatement,
    StoreStatement,
    ReadWorkFileStatement,
    WriteWorkFileStatement,
    CloseWorkFileStatement,
)
from natural.ir.semantic import (
    SemanticModule,
    Symbol,
    SemanticType,
    AssignOp,
    BranchOp,
    LoopOp,
    ForLoopOp,
    BreakOp,
    ReturnOp,
    ContinueOp,
    QueryIterationOp,
    SemanticExpression,
    CompressOp,
    ExamineOp,
    ResetOp,
    CallSubroutineOp,
    EntityUpdateOp,
    EntityStoreOp,
    EntityDeleteOp,
    ReadWorkFileOp,
    WriteWorkFileOp,
    CloseWorkFileOp,
    SubroutineBlockOp,
)
from natural.normalizer.workspace import Workspace


class ActiveLoopContext:
    def __init__(self, loop_id: str, label: Optional[str] = None, entity: Optional[str] = None):
        self.loop_id = loop_id
        self.label = label.upper() if label else None
        self.entity = entity


class SemanticLoweringPass:
    def __init__(self, ast: NaturalModule, workspace: Optional[Workspace] = None):
        self.ast = ast
        self.workspace = workspace
        self.symbols: Dict[str, Symbol] = {}
        self.loop_stack: List[ActiveLoopContext] = []
        self.loop_counter = 0

    def parse_format(self, raw_fmt: str) -> SemanticType:
        if not raw_fmt:
            return SemanticType(base="unknown")
        raw_fmt = raw_fmt.strip("()")
        kind = raw_fmt[0]
        if kind in ("P", "N"):
            parts = raw_fmt[1:].split(".")
            prec = int(parts[0]) if parts[0].isdigit() else 0
            scale = int(parts[1]) if len(parts) > 1 else 0
            storage = "packed_decimal" if kind == "P" else "unpacked_decimal"
            return SemanticType(base="decimal", precision=prec, scale=scale, storage=storage)
        elif kind == "A":
            length = int(raw_fmt[1:]) if raw_fmt[1:].isdigit() else 0
            return SemanticType(base="string", length=length, storage="alphanumeric")
        elif kind == "D":
            return SemanticType(base="date", length=8, storage="date")
        elif kind == "L":
            return SemanticType(base="boolean", length=1, storage="boolean")
        elif kind in ("I", "B"):
            length = int(raw_fmt[1:]) if raw_fmt[1:].isdigit() else 4
            return SemanticType(base="integer", length=length, storage="binary")
        return SemanticType(base="unknown", storage=raw_fmt)

    def _field_length(self, sem_type: SemanticType) -> int:
        if sem_type.base == "string" and sem_type.length:
            return sem_type.length
        elif sem_type.base == "decimal" and sem_type.precision:
            return sem_type.precision
        elif sem_type.base == "integer":
            return sem_type.length or 4
        elif sem_type.base == "date":
            return sem_type.length or 8
        elif sem_type.base == "boolean":
            return 1
        return sem_type.length or sem_type.precision or 1

    def build_symbol_table(self):
        import sys
        redefine_offsets: Dict[str, int] = {}

        for area in self.ast.data_areas:
            fields = area.inline_fields

            if not fields and self.workspace:
                ext_area = self.workspace.get_data_area(area.name, area.scope)
                if ext_area:
                    fields = ext_area.inline_fields
                else:
                    print(
                        f"[Compiler Warning] Unable to resolve {area.scope.value} USING {area.name}.",
                        file=sys.stderr,
                    )

            for field in fields:
                clean_name = field.name.lower().replace("#", "")
                sym_id = f"sym.{area.scope.value.lower()}.{clean_name}"
                raw_spec = field.format.raw_spec if field.format else "A"
                sem_type = self.parse_format(raw_spec)

                parent_id = None
                offset = 0
                if field.parent_name:
                    parent_clean = field.parent_name.lower().replace("#", "")
                    parent_id = f"sym.{area.scope.value.lower()}.{parent_clean}"
                    offset = redefine_offsets.get(parent_id, 0)
                    redefine_offsets[parent_id] = offset + self._field_length(sem_type)

                sym = Symbol(
                    id=sym_id,
                    name=field.name,
                    scope=area.scope.value.lower(),
                    semantic_type=sem_type,
                    redefine_parent=parent_id,
                    redefine_offset=offset,
                )
                self.symbols[field.name] = sym

                if field.parent_name:
                    qualified = f"{field.parent_name}.{field.name}"
                    self.symbols[qualified] = sym

    def resolve_ref(self, name: str) -> str:
        if name in self.symbols:
            return self.symbols[name].id
        clean = name.split(".")[-1].lower().replace("#", "")
        for sym in self.symbols.values():
            if sym.name.lower().replace("#", "") == clean:
                return sym.id
        return f"sym.unresolved.{name.lower().replace('#', '').replace('.', '_')}"

    def lower_expr(self, expr: Expression) -> SemanticExpression:
        if expr.kind == "ref":
            return SemanticExpression(op="ref", symbol_id=self.resolve_ref(expr.value))
        elif expr.kind == "literal":
            return SemanticExpression(op="literal", value=expr.value)
        elif expr.kind == "sys_var":
            var_name = str(expr.value).upper()
            if var_name.startswith("*COUNTER"):
                return SemanticExpression(op="counter", value="loop_counter")
            elif var_name.startswith("*ISN"):
                return SemanticExpression(op="ref", symbol_id="sym.entity.active.id")
            elif var_name.startswith("*NUMBER"):
                return SemanticExpression(op="literal", value=1)
            elif var_name in ("*DATX", "*DATN"):
                return SemanticExpression(op="sys_date", value="date.today()")
            elif var_name == "*TIME":
                return SemanticExpression(op="sys_time", value="datetime.now().time()")
            return SemanticExpression(op="literal", value=var_name)
        elif expr.kind == "binary_op":
            op_map = {
                "*": "multiply", "+": "add", "-": "subtract", "/": "divide",
                ">": "gt", "<": "lt", "=": "eq", ">=": "gte", "<=": "lte", "<>": "neq",
                "AND": "and", "OR": "or",
            }
            return SemanticExpression(
                op=op_map.get(expr.operator, expr.operator.lower() if expr.operator else "unknown"),
                lhs=self.lower_expr(expr.left) if expr.left else None,
                rhs=self.lower_expr(expr.right) if expr.right else None,
            )
        return SemanticExpression(op="unknown")

    def _resolve_target_loop(self, label: Optional[str]) -> str:
        if not self.loop_stack:
            return "unknown_loop"
        if not label:
            return self.loop_stack[-1].loop_id
        target = label.upper().rstrip(".")
        for ctx in reversed(self.loop_stack):
            if ctx.label == target:
                return ctx.loop_id
        return self.loop_stack[-1].loop_id

    def lower_statement(self, stmt) -> list:
        if isinstance(stmt, AssignStatement):
            return [
                AssignOp(
                    target_id=self.resolve_ref(stmt.target),
                    expr=self.lower_expr(stmt.value),
                )
            ]
        elif isinstance(stmt, MoveStatement):
            target_str = str(stmt.target.value) if hasattr(stmt.target, "value") else str(stmt.target)
            return [
                AssignOp(
                    target_id=self.resolve_ref(target_str),
                    expr=self.lower_expr(stmt.source),
                    edit_mask=stmt.edit_mask,
                )
            ]
        elif isinstance(stmt, CompressStatement):
            target_str = str(stmt.target.value) if hasattr(stmt.target, "value") else str(stmt.target)
            return [
                CompressOp(
                    target_id=self.resolve_ref(target_str),
                    operands=[self.lower_expr(op) for op in stmt.operands],
                    delimiter=self.lower_expr(stmt.delimiter) if stmt.delimiter else None,
                    with_delimiters=stmt.with_delimiters,
                )
            ]
        elif isinstance(stmt, ExamineStatement):
            target_str = str(stmt.target.value) if hasattr(stmt.target, "value") else str(stmt.target)
            giving_id = self.resolve_ref(str(stmt.giving_number.value)) if stmt.giving_number else None
            return [
                ExamineOp(
                    target_id=self.resolve_ref(target_str),
                    pattern=self.lower_expr(stmt.pattern),
                    replace_with=self.lower_expr(stmt.replace_with) if stmt.replace_with else None,
                    giving_number_id=giving_id,
                )
            ]
        elif isinstance(stmt, ResetStatement):
            ops = []
            for t in stmt.targets:
                target_str = str(t.value) if hasattr(t, "value") else str(t)
                ops.append(ResetOp(target_id=self.resolve_ref(target_str), initial=stmt.initial))
            return ops
        elif isinstance(stmt, PerformStatement):
            return [CallSubroutineOp(subroutine_name=stmt.subroutine_name)]
        elif isinstance(stmt, UpdateStatement):
            target_loop_id = self._resolve_target_loop(stmt.loop_label)
            matched_entity = "active_record"
            for ctx in reversed(self.loop_stack):
                if ctx.loop_id == target_loop_id and ctx.entity:
                    matched_entity = ctx.entity
                    break
            return [EntityUpdateOp(target_loop_id=target_loop_id, entity=matched_entity)]
        elif isinstance(stmt, DeleteStatement):
            target_loop_id = self._resolve_target_loop(stmt.loop_label)
            matched_entity = "active_record"
            for ctx in reversed(self.loop_stack):
                if ctx.loop_id == target_loop_id and ctx.entity:
                    matched_entity = ctx.entity
                    break
            return [EntityDeleteOp(target_loop_id=target_loop_id, entity=matched_entity)]
        elif isinstance(stmt, StoreStatement):
            entity_name = stmt.view_name.replace("-VIEW", "")
            return [EntityStoreOp(entity=entity_name, natural_view=stmt.view_name)]
        elif isinstance(stmt, WriteWorkFileStatement):
            return [
                WriteWorkFileOp(
                    file_number=stmt.file_number,
                    operands=[self.lower_expr(f) for f in stmt.fields],
                )
            ]
        elif isinstance(stmt, CloseWorkFileStatement):
            return [CloseWorkFileOp(file_number=stmt.file_number)]
        elif isinstance(stmt, ReadWorkFileStatement):
            self.loop_counter += 1
            loop_id = f"loop.workfile_{self.loop_counter:03d}"
            self.loop_stack.append(ActiveLoopContext(loop_id=loop_id, label=stmt.label))

            targets = [self.resolve_ref(str(f.value)) for f in stmt.fields]
            body_ops = self.lower_statements(stmt.body)

            self.loop_stack.pop()
            return [
                ReadWorkFileOp(
                    id=loop_id,
                    label=stmt.label,
                    file_number=stmt.file_number,
                    target_ids=targets,
                    body=body_ops,
                )
            ]
        elif isinstance(stmt, ConditionalStatement):
            return [
                BranchOp(
                    condition=self.lower_expr(stmt.condition),
                    then_branch=self.lower_statements(stmt.then_branch),
                    else_branch=self.lower_statements(stmt.else_branch),
                )
            ]
        elif isinstance(stmt, DecideStatement):
            if not stmt.branches:
                return self.lower_statements(stmt.none_branch)

            root_branch = None
            current_branch = None
            operand_expr = self.lower_expr(stmt.operand) if stmt.operand else None

            for branch in stmt.branches:
                if stmt.decide_type == "ON" and operand_expr:
                    condition = SemanticExpression(
                        op="eq",
                        lhs=operand_expr,
                        rhs=self.lower_expr(branch.value),
                    )
                else:
                    condition = self.lower_expr(branch.value)

                new_branch = BranchOp(
                    condition=condition,
                    then_branch=self.lower_statements(branch.statements),
                    else_branch=[],
                )

                if not root_branch:
                    root_branch = new_branch
                    current_branch = new_branch
                else:
                    current_branch.else_branch = [new_branch]
                    current_branch = new_branch

            if stmt.none_branch and current_branch:
                current_branch.else_branch = self.lower_statements(stmt.none_branch)

            return [root_branch] if root_branch else []

        elif isinstance(stmt, LoopStatement):
            self.loop_counter += 1
            loop_id = f"loop.repeat_{self.loop_counter:03d}"
            self.loop_stack.append(ActiveLoopContext(loop_id=loop_id, label=stmt.label))

            cond = self.lower_expr(stmt.condition) if stmt.condition else None
            body_ops = self.lower_statements(stmt.body)

            self.loop_stack.pop()
            return [
                LoopOp(
                    id=loop_id,
                    label=stmt.label,
                    loop_type=stmt.loop_type.lower() if hasattr(stmt, "loop_type") else ("until" if cond else "infinite"),
                    condition=cond,
                    body=body_ops,
                )
            ]
        elif isinstance(stmt, ForStatement):
            self.loop_counter += 1
            loop_id = f"loop.for_{self.loop_counter:03d}"
            self.loop_stack.append(ActiveLoopContext(loop_id=loop_id, label=stmt.label))

            step_op = self.lower_expr(stmt.step_expr) if stmt.step_expr else SemanticExpression(op="literal", value=1)
            body_ops = self.lower_statements(stmt.body)

            self.loop_stack.pop()
            return [
                ForLoopOp(
                    id=loop_id,
                    label=stmt.label,
                    variable_id=self.resolve_ref(stmt.variable),
                    start=self.lower_expr(stmt.start_expr),
                    end=self.lower_expr(stmt.end_expr),
                    step=step_op,
                    body=body_ops,
                )
            ]
        elif isinstance(stmt, (FindStatement, ReadStatement)):
            self.loop_counter += 1
            op_name = "find" if isinstance(stmt, FindStatement) else "read"
            loop_id = f"loop.{op_name}_{self.loop_counter:03d}"
            entity_name = stmt.view_name.replace("-VIEW", "")
            self.loop_stack.append(ActiveLoopContext(loop_id=loop_id, label=stmt.label, entity=entity_name))

            if self.workspace:
                ddm = self.workspace.get_ddm(stmt.view_name)
                if ddm:
                    for field in ddm.inline_fields:
                        clean_name = field.name.lower()
                        sym_id = f"sym.entity.{stmt.view_name.lower()}.{clean_name}"
                        raw_spec = field.format.raw_spec if field.format else "A"
                        self.symbols[field.name] = Symbol(
                            id=sym_id,
                            name=field.name,
                            scope="entity_field",
                            semantic_type=self.parse_format(raw_spec),
                        )

            limit_val = getattr(stmt, "limit", None)
            cardinality = "one" if limit_val == 1 else "many"

            if isinstance(stmt, FindStatement):
                predicate = SemanticExpression(
                    op="eq",
                    lhs=SemanticExpression(
                        op="entity_field",
                        symbol_id=f"sym.entity.{stmt.view_name.lower()}.{stmt.descriptor.lower()}",
                    ),
                    rhs=self.lower_expr(stmt.operand),
                )
                on_empty = self.lower_statements(stmt.on_empty)
            else:
                predicate = SemanticExpression(op="literal", value=True)
                if getattr(stmt, "starting_from", None) and getattr(stmt, "by_descriptor", None):
                    predicate = SemanticExpression(
                        op="gte",
                        lhs=SemanticExpression(
                            op="entity_field",
                            symbol_id=f"sym.entity.{stmt.view_name.lower()}.{stmt.by_descriptor.lower()}",
                        ),
                        rhs=self.lower_expr(stmt.starting_from),
                    )
                on_empty = []

            op = QueryIterationOp(
                id=loop_id,
                label=stmt.label,
                entity=entity_name,
                natural_view=stmt.view_name,
                predicate=predicate,
                limit=limit_val,
                cardinality=cardinality,
                body=self.lower_statements(stmt.body),
                on_empty=on_empty,
            )
            self.loop_stack.pop()
            return [op]
        elif isinstance(stmt, EscapeStatement):
            if stmt.target == "ROUTINE":
                return [ReturnOp()]

            target_id = self._resolve_target_loop(stmt.loop_label)
            if stmt.target == "BOTTOM":
                return [BreakOp(target_loop_id=target_id)]
            elif stmt.target == "TOP":
                return [ContinueOp(target_loop_id=target_id)]
            return []
        return []

    def lower_statements(self, stmts) -> list:
        res = []
        for s in stmts:
            res.extend(self.lower_statement(s))
        return res

    def lower(self) -> SemanticModule:
        self.build_symbol_table()
        ops = self.lower_statements(self.ast.body)

        subs = {}
        for sub_name, stmts in self.ast.subroutines.items():
            subs[sub_name] = SubroutineBlockOp(name=sub_name, operations=self.lower_statements(stmts))

        return SemanticModule(
            module_id=f"mod.{self.ast.name.lower()}",
            symbols=self.symbols,
            operations=ops,
            subroutines=subs,
        )
