# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
#
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import List, Dict, Optional
from natural.ir.models import (
    NaturalModule,
    AssignStatement,
    FindStatement,
    ConditionalStatement,
    EscapeStatement,
    Expression,
    LoopStatement,
    MoveStatement,
    PrintStatement,
    InputStatement,
)
from natural.ir.semantic import (
    SemanticModule,
    Symbol,
    SemanticType,
    AssignOp,
    BranchOp,
    LoopOp,
    BreakOp,
    ReturnOp,
    ContinueOp,
    QueryIterationOp,
    SemanticExpression,
)
from natural.normalizer.workspace import Workspace


class SemanticLoweringPass:
    def __init__(self, ast: NaturalModule, workspace: Optional[Workspace] = None):
        self.ast = ast
        self.workspace = workspace
        self.symbols: Dict[str, Symbol] = {}
        self.loop_stack: List[str] = []
        self.loop_counter = 0

    def parse_format(self, raw_fmt: str) -> SemanticType:
        if not raw_fmt:
            return SemanticType(base="unknown")
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
            return SemanticType(base="date", storage="date")
        elif kind == "L":
            return SemanticType(base="boolean", storage="boolean")
        elif kind in ("I", "B"):
            return SemanticType(base="integer", storage="binary")
        return SemanticType(base="unknown", storage=raw_fmt)

    def _field_length(self, sem_type: SemanticType) -> int:
        if sem_type.base == "decimal" and sem_type.precision:
            return sem_type.precision
        elif sem_type.base == "string" and sem_type.length:
            return sem_type.length
        return 2

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
                sem_type = self.parse_format(field.format.raw_spec)

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

                # Register qualified alias (e.g. #DATEA.DD -> sym.local.dd)
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
        elif expr.kind == "binary_op":
            op_map = {
                "*": "multiply",
                "+": "add",
                "-": "subtract",
                "/": "divide",
                ">": "gt",
                "<": "lt",
                "=": "eq",
                ">=": "gte",
                "<=": "lte",
                "<>": "neq",
            }
            return SemanticExpression(
                op=op_map.get(expr.operator, expr.operator),
                lhs=self.lower_expr(expr.left) if expr.left else None,
                rhs=self.lower_expr(expr.right) if expr.right else None,
            )
        return SemanticExpression(op="unknown")

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
        elif isinstance(stmt, ConditionalStatement):
            return [
                BranchOp(
                    condition=self.lower_expr(stmt.condition),
                    then_branch=self.lower_statements(stmt.then_branch),
                    else_branch=self.lower_statements(stmt.else_branch),
                )
            ]
        elif isinstance(stmt, LoopStatement):
            self.loop_counter += 1
            loop_id = f"loop.repeat_{self.loop_counter:03d}"
            self.loop_stack.append(loop_id)

            cond = self.lower_expr(stmt.condition) if stmt.condition else None
            body_ops = self.lower_statements(stmt.body)

            self.loop_stack.pop()
            return [
                LoopOp(
                    id=loop_id,
                    loop_type="until" if cond else "infinite",
                    condition=cond,
                    body=body_ops,
                )
            ]
        elif isinstance(stmt, FindStatement):
            self.loop_counter += 1
            loop_id = f"loop.find_{self.loop_counter:03d}"
            self.loop_stack.append(loop_id)

            if self.workspace:
                ddm = self.workspace.get_ddm(stmt.view_name)
                if ddm:
                    for field in ddm.inline_fields:
                        clean_name = field.name.lower()
                        sym_id = f"sym.entity.{stmt.view_name.lower()}.{clean_name}"
                        self.symbols[field.name] = Symbol(
                            id=sym_id,
                            name=field.name,
                            scope="entity_field",
                            semantic_type=self.parse_format(field.format.raw_spec),
                        )

            op = QueryIterationOp(
                id=loop_id,
                entity=stmt.view_name.replace("-VIEW", ""),
                natural_view=stmt.view_name,
                predicate=SemanticExpression(
                    op="eq",
                    lhs=SemanticExpression(
                        op="entity_field",
                        symbol_id=f"sym.entity.{stmt.view_name.lower()}.{stmt.descriptor.lower()}",
                    ),
                    rhs=self.lower_expr(stmt.operand),
                ),
                body=self.lower_statements(stmt.body),
                on_empty=self.lower_statements(stmt.on_empty),
            )
            self.loop_stack.pop()
            return [op]
        elif isinstance(stmt, EscapeStatement):
            if stmt.target == "ROUTINE":
                return [ReturnOp()]

            target_id = self.loop_stack[-1] if self.loop_stack else "unknown_loop"
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
        return SemanticModule(
            module_id=f"mod.{self.ast.name.lower()}",
            symbols=self.symbols,
            operations=ops,
        )
