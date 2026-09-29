# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import re
from typing import Callable, Dict, List, Optional, Type
from natural.ir.models import Expression, FunctionDefinition, NaturalModule, Statement, SubroutineDefinition
from natural.ir.semantic import FunctionBlockOp, OnErrorOp, SemanticExpression, SemanticModule, SemanticStatement, SemanticType, SubroutineBlockOp, Symbol
from natural.normalizer.lowering.context import LoweringContext
from natural.normalizer.lowering.expressions import ExpressionLowerer
from natural.normalizer.lowering.handlers import DEFAULT_HANDLERS
from natural.normalizer.workspace import Workspace


class SemanticLoweringPass:
    """Pass 3: Lowers Syntactic AST (IR0) into a Semantic DAG (IR1)."""

    def __init__(
            self,
            ast: NaturalModule,
            workspace: Optional[Workspace] = None,
            handlers: Optional[Dict[Type[Statement], Callable]] = None,
    ):
        self.ast = ast
        self.workspace = workspace
        self.ctx = LoweringContext(ast, workspace=workspace)
        self.expr_lowerer = ExpressionLowerer(self.ctx)
        self.handlers = handlers or DEFAULT_HANDLERS

    @property
    def symbols(self) -> Dict[str, Symbol]:
        return self.ctx.symbols

    @property
    def loop_stack(self):
        return self.ctx.loop_stack

    @property
    def loop_counter(self) -> int:
        return self.ctx.loop_counter

    @loop_counter.setter
    def loop_counter(self, val: int):
        self.ctx.loop_counter = val

    def resolve_ref(self, name: str) -> str:
        return self.ctx.resolve_ref(name)

    def lower_expr(self, expr: Expression) -> SemanticExpression:
        return self.expr_lowerer.lower(expr)

    def parse_format(self, raw_fmt: str) -> SemanticType:
        return self.ctx.parse_format(raw_fmt)

    def build_symbol_table(self) -> None:
        self.ctx.build_symbol_table()

    def lower_statement(self, stmt: Statement) -> List[SemanticStatement]:
        handler = self.handlers.get(type(stmt))
        if handler:
            return handler(stmt, self.ctx, self.expr_lowerer, self)
        return []

    def lower_statements(self, stmts: List[Statement]) -> List[SemanticStatement]:
        res = []
        for s in stmts:
            res.extend(self.lower_statement(s))
        return res

    def lower_function(self, fn_name: str, fn_def: FunctionDefinition) -> FunctionBlockOp:
        clean_raw_fmt = ""
        if fn_def.returns_raw:
            m = re.search(r"\(([^)]+)\)", fn_def.returns_raw)
            clean_raw_fmt = m.group(1) if m else fn_def.returns_raw.replace("RETURNS", "").strip()
        ret_type = self.ctx.parse_format(clean_raw_fmt)

        saved_active = self.ctx.active_function_name
        saved_func_syms = self.ctx.function_symbols

        self.ctx.active_function_name = fn_name
        self.ctx.function_symbols = {}

        param_symbols: List[Symbol] = []
        for p in fn_def.parameters:
            clean_p = p.name.lower().replace("#", "")
            sym_id = f"fn.{fn_name.lower()}.{clean_p}"
            raw_spec = p.format.raw_spec if p.format else "A"
            is_arr = bool(p.array_dim or getattr(p, "is_periodic", False) or getattr(p, "is_multiple", False))
            sym = Symbol(
                id=sym_id,
                name=p.name,
                scope="parameter",
                semantic_type=self.ctx.parse_format(raw_spec),
                is_array=is_arr,
            )
            self.ctx.function_symbols[p.name] = sym
            param_symbols.append(sym)

        ops = self.lower_statements(fn_def.body)

        self.ctx.active_function_name = saved_active
        self.ctx.function_symbols = saved_func_syms

        return FunctionBlockOp(
            name=fn_name,
            return_type=ret_type,
            parameters=param_symbols,
            operations=ops,
        )

    def lower(self) -> SemanticModule:
        self.build_symbol_table()
        ops = self.lower_statements(self.ast.body)

        subs = {}
        for sub_name, sub_item in self.ast.subroutines.items():
            if isinstance(sub_item, SubroutineDefinition):
                ops_sub = self.lower_statements(sub_item.body)
                on_err_op = (
                    OnErrorOp(body=self.lower_statements(sub_item.on_error.body))
                    if sub_item.on_error
                    else None
                )
                subs[sub_name] = SubroutineBlockOp(
                    name=sub_name,
                    operations=ops_sub,
                    on_error=on_err_op,
                )
            else:
                subs[sub_name] = SubroutineBlockOp(
                    name=sub_name,
                    operations=self.lower_statements(sub_item),
                )

        funcs = {}
        for fn_name, fn_def in self.ast.functions.items():
            funcs[fn_name] = self.lower_function(fn_name, fn_def)

        return SemanticModule(
            module_id=f"mod.{self.ast.name.lower()}",
            symbols=self.ctx.symbols,
            operations=ops,
            subroutines=subs,
            functions=funcs,
        )
