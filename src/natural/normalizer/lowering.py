# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
#
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import List, Dict, Optional
from natural.ir.models import (
    NaturalModule, AssignStatement, FindStatement,
    ConditionalStatement, EscapeStatement, Expression
)
from natural.ir.semantic import (
    SemanticModule, Symbol, SemanticType, AssignOp, BranchOp,
    BreakOp, ReturnOp, ContinueOp, QueryIterationOp, SemanticExpression
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
        if kind in ('P', 'N'):
            parts = raw_fmt[1:].split('.')
            prec = int(parts[0]) if parts[0].isdigit() else 0
            scale = int(parts[1]) if len(parts) > 1 else 0
            storage = "packed_decimal" if kind == 'P' else "unpacked_decimal"
            return SemanticType(base="decimal", precision=prec, scale=scale, storage=storage)
        elif kind == 'A':
            length = int(raw_fmt[1:]) if raw_fmt[1:].isdigit() else 0
            return SemanticType(base="string", length=length, storage="alphanumeric")
        return SemanticType(base="unknown", storage=raw_fmt)

    def build_symbol_table(self):
        import sys  # Added for stderr printing

        for area in self.ast.data_areas:
            fields = area.inline_fields

            # Request external file definitions if empty
            if not fields and self.workspace:
                ext_area = self.workspace.get_data_area(area.name, area.scope)
                if ext_area:
                    fields = ext_area.inline_fields
                else:
                    print(f"[Compiler Warning] Unable to resolve {area.scope.value} USING {area.name}. "
                          f"Ensure file exists in workspace. Symbols will remain unresolved.", file=sys.stderr)

            for field in fields:
                clean_name = field.name.lower().replace('#', '')
                sym_id = f"sym.{area.scope.value.lower()}.{clean_name}"
                self.symbols[field.name] = Symbol(
                    id=sym_id,
                    name=field.name,
                    scope=area.scope.value.lower(),
                    semantic_type=self.parse_format(field.format.raw_spec)
                )

    def resolve_ref(self, name: str) -> str:
        if name in self.symbols:
            return self.symbols[name].id
        return f"sym.unresolved.{name.lower().replace('#', '')}"

    def lower_expr(self, expr: Expression) -> SemanticExpression:
        if expr.kind == "ref":
            return SemanticExpression(op="ref", symbol_id=self.resolve_ref(expr.value))
        elif expr.kind == "literal":
            return SemanticExpression(op="literal", value=expr.value)
        elif expr.kind == "binary_op":
            op_map = {"*": "multiply", "+": "add", "-": "subtract", ">": "gt", "<": "lt", "=": "eq", ">=": "gte"}
            return SemanticExpression(
                op=op_map.get(expr.operator, expr.operator),
                lhs=self.lower_expr(expr.left) if expr.left else None,
                rhs=self.lower_expr(expr.right) if expr.right else None
            )
        return SemanticExpression(op="unknown")

    def lower_statement(self, stmt) -> list:
        if isinstance(stmt, AssignStatement):
            return [AssignOp(
                target_id=self.resolve_ref(stmt.target),
                expr=self.lower_expr(stmt.value)
            )]
        elif isinstance(stmt, ConditionalStatement):
            return [BranchOp(
                condition=self.lower_expr(stmt.condition),
                then_branch=self.lower_statements(stmt.then_branch),
                else_branch=self.lower_statements(stmt.else_branch)
            )]
        elif isinstance(stmt, FindStatement):
            self.loop_counter += 1
            loop_id = f"loop.find_{self.loop_counter:03d}"
            self.loop_stack.append(loop_id)

            # Pre-load DDM entity fields into active scope so unqualified body references succeed
            if self.workspace:
                ddm = self.workspace.get_ddm(stmt.view_name)
                if ddm:
                    for field in ddm.inline_fields:
                        clean_name = field.name.lower()
                        sym_id = f"sym.entity.{stmt.view_name.lower()}.{clean_name}"
                        # Inject directly into active symbol scope
                        self.symbols[field.name] = Symbol(
                            id=sym_id,
                            name=field.name,
                            scope="entity_field",
                            semantic_type=self.parse_format(field.format.raw_spec)
                        )

            op = QueryIterationOp(
                id=loop_id,
                entity=stmt.view_name.replace('-VIEW', ''),
                natural_view=stmt.view_name,
                predicate=SemanticExpression(
                    op="eq",
                    lhs=SemanticExpression(op="entity_field", symbol_id=f"sym.entity.{stmt.view_name.lower()}.{stmt.descriptor.lower()}"),
                    rhs=self.lower_expr(stmt.operand)
                ),
                body=self.lower_statements(stmt.body),
                on_empty=self.lower_statements(stmt.on_empty)
            )
            self.loop_stack.pop()
            return [op]
        elif isinstance(stmt, EscapeStatement):
            if stmt.target == "ROUTINE":
                return [ReturnOp()]

            # Target the innermost active loop for BOTTOM/TOP
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
            operations=ops
        )
