# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import Callable, Dict, List, Optional, Type
from natural.ir.semantic import OnErrorOp, SemanticExpression, SemanticModule, SemanticStatement, SemanticType, Symbol
from natural.codegen.targets.python.context import EmitterContext
from natural.codegen.targets.python.expressions import PythonExpressionEmitter
from natural.codegen.targets.python.formatters import convert_edit_mask, format_numeric_edit_mask
from natural.codegen.targets.python.handlers import DEFAULT_OPERATION_HANDLERS
from natural.codegen.targets.python.harvester import ImportHarvester


class PythonEmitter:
    """Pass 4: Generates typed Python business logic and execution scaffolding from IR1."""

    def __init__(
            self,
            module: SemanticModule,
            handlers: Optional[Dict[Type[SemanticStatement], Callable]] = None,
    ):
        self.module = module
        self.ctx = EmitterContext(module)
        self.expr_emitter = PythonExpressionEmitter(self.ctx)
        self.harvester = ImportHarvester(self.ctx)
        self.handlers = handlers or DEFAULT_OPERATION_HANDLERS
        self._sym_by_id = self.ctx._sym_by_id

    @property
    def lines(self) -> List[str]:
        return self.ctx.lines

    @property
    def indent_level(self) -> int:
        return self.ctx.indent_level

    @indent_level.setter
    def indent_level(self, val: int):
        self.ctx.indent_level = val

    @property
    def current_loop_views(self) -> List[str]:
        return self.ctx.current_loop_views

    @current_loop_views.setter
    def current_loop_views(self, views: List[str]):
        self.ctx.current_loop_views = views

    def emit_line(self, line: str) -> None:
        self.ctx.emit_line(line)

    def _clean_name(self, name: str) -> str:
        return self.ctx.clean_name(name)

    def _clean_func_name(self, name: str) -> str:
        return self.ctx.clean_func_name(name)

    def _to_pascal_case(self, name: str) -> str:
        return self.ctx.to_pascal_case(name)

    def _resolve_ref(self, symbol_id: str, model_class: Optional[str] = None) -> str:
        return self.ctx.resolve_ref(symbol_id, model_class=model_class)

    def emit_expr(self, expr: SemanticExpression, model_class: Optional[str] = None) -> str:
        return self.expr_emitter.emit_expr(expr, model_class=model_class)

    def _convert_edit_mask(self, mask: str) -> str:
        return convert_edit_mask(mask)

    def _format_numeric_edit_mask(self, target: str, src_ref: str, mask: str) -> str:
        return format_numeric_edit_mask(target, src_ref, mask)

    def _collect_required_imports(self, emit_main: bool = False) -> List[str]:
        return self.harvester.collect_required_imports(emit_main=emit_main)

    def _type_to_python_hint(self, sem_type: SemanticType) -> str:
        return self.ctx.type_to_python_hint(sem_type)

    def emit_operation(self, op: SemanticStatement) -> None:
        handler = self.handlers.get(type(op))
        if handler:
            handler(op, self.ctx, self.expr_emitter, self)

    def emit_main_block(self, class_name: str, func_name: str) -> None:
        self.emit_line("")
        self.emit_line('if __name__ == "__main__":')
        with self.ctx.indent():
            self.emit_line("import sys")
            self.emit_line("import argparse")
            self.emit_line("")
            self.emit_line(f'parser = argparse.ArgumentParser(description="Standalone runner for {func_name}")')

            unique_syms = {s.id: s for s in self.module.symbols.values()}
            independent_syms = [
                s for s in unique_syms.values()
                if not s.redefine_parent and s.scope != "entity_field"
            ]
            for sym in independent_syms:
                py_name = self.ctx.clean_name(sym.name)
                kebab_flag = f"--{py_name.replace('_', '-')}"
                snake_flag = f"--{py_name}"
                flags = f'"{kebab_flag}", "{snake_flag}"' if kebab_flag != snake_flag else f'"{kebab_flag}"'

                self.emit_line(
                    f'parser.add_argument({flags}, dest="{py_name}", type=str, default=None, help="Initial value for {py_name}")'
                )

            self.emit_line("args = parser.parse_args()")
            self.emit_line(f"ctx = {class_name}()")
            self.emit_line("")

            for sym in independent_syms:
                py_name = self.ctx.clean_name(sym.name)
                base_type = sym.semantic_type.base
                self.emit_line(f"if args.{py_name} is not None:")
                with self.ctx.indent():
                    if getattr(sym, "is_array", False):
                        self.emit_line(f"ctx.{py_name} = {{str(i): v for i, v in enumerate(args.{py_name}.split(','), 1)}}")
                    elif base_type == "date":
                        self.emit_line(f"ctx.{py_name} = date.fromisoformat(args.{py_name})")
                    elif base_type == "decimal":
                        self.emit_line(f"ctx.{py_name} = Decimal(args.{py_name})")
                    elif base_type == "integer":
                        self.emit_line(f"ctx.{py_name} = int(args.{py_name})")
                    elif base_type == "boolean":
                        self.emit_line(f'ctx.{py_name} = args.{py_name}.lower() in ("true", "1", "yes", "t")')
                    else:
                        self.emit_line(f"ctx.{py_name} = args.{py_name}")

            self.emit_line("")
            self.emit_line("class MockQuery(list):")
            with self.ctx.indent():
                self.emit_line("def filter(self, *args, **kwargs):")
                with self.ctx.indent():
                    self.emit_line("return self")
                self.emit_line("def limit(self, *args, **kwargs):")
                with self.ctx.indent():
                    self.emit_line("return self")
                self.emit_line("def group_by(self, *args, **kwargs):")
                with self.ctx.indent():
                    self.emit_line("return self")
                self.emit_line("def all(self):")
                with self.ctx.indent():
                    self.emit_line("return self")

            self.emit_line("")
            self.emit_line("class MockSession:")
            with self.ctx.indent():
                self.emit_line("def query(self, *args, **kwargs):")
                with self.ctx.indent():
                    self.emit_line("return MockQuery()")
                self.emit_line("def get(self, entity, ident):")
                with self.ctx.indent():
                    self.emit_line("return entity()")
                self.emit_line("def add(self, obj): pass")
                self.emit_line("def delete(self, obj): pass")
                self.emit_line("def flush(self): pass")
                self.emit_line("def commit(self): pass")
                self.emit_line("def rollback(self): pass")
                self.emit_line("def refresh(self, obj): pass")

            self.emit_line("")
            self.emit_line("session = MockSession()")
            self.emit_line(f"result = {func_name}(ctx, session)")
            self.emit_line("")
            self.emit_line(f'print(f"[{func_name}] Execution complete:")')
            self.emit_line("for k, v in sorted(result.__dict__.items()):")
            with self.ctx.indent():
                self.emit_line('if not k.startswith("_"):')
                with self.ctx.indent():
                    self.emit_line('print(f"  {k}: {v}")')

            redefined_syms = [s for s in unique_syms.values() if s.redefine_parent]
            for r_sym in sorted(redefined_syms, key=lambda s: s.redefine_offset):
                prop_name = self.ctx.clean_name(r_sym.name)
                self.emit_line(f'print(f"  {prop_name} (redefine): {{getattr(result, \'{prop_name}\')}}")')

    def generate(self, emit_main: bool = False) -> str:
        import_lines = self.harvester.collect_required_imports(emit_main=emit_main)
        for imp in import_lines:
            self.emit_line(imp)

        callnat_imports, orm_models, needs_func = self.harvester.collect_module_metadata()

        for prog in sorted(callnat_imports):
            items = ", ".join(sorted(callnat_imports[prog]))
            self.emit_line(f"from {prog} import {items}")

        if needs_func:
            self.emit_line("from sqlalchemy import func")
        if orm_models:
            self.emit_line(f"from target_orm import {', '.join(sorted(orm_models))}")

        if import_lines or callnat_imports or orm_models or needs_func:
            self.emit_line("")

        for fn_name, fn_block in self.module.functions.items():
            py_fn_name = self.ctx.clean_func_name(fn_name)
            params_list = [f"{self.ctx.clean_name(p.name)}: {self.ctx.type_to_python_hint(p.semantic_type)}" for p in fn_block.parameters]
            ret_hint = self.ctx.type_to_python_hint(fn_block.return_type)
            self.emit_line(f"def {py_fn_name}({', '.join(params_list)}) -> {ret_hint}:")
            with self.ctx.indent():
                if not fn_block.operations:
                    self.emit_line("pass")
                for op in fn_block.operations:
                    self.emit_operation(op)
            self.emit_line("")

        class_name = self.ctx.to_pascal_case(self.module.module_id) + "Context"
        self.emit_line(f"class {class_name}:")
        with self.ctx.indent():
            unique_syms = {s.id: s for s in self.module.symbols.values()}
            independent_syms = [
                s for s in unique_syms.values()
                if not s.redefine_parent and s.scope != "entity_field"
            ]
            redefined_syms = [s for s in unique_syms.values() if s.redefine_parent]

            self.emit_line("def __init__(self):")
            with self.ctx.indent():
                for sym in independent_syms:
                    py_name = self.ctx.clean_name(sym.name)
                    base = sym.semantic_type.base
                    if getattr(sym, "is_array", False):
                        default = "{}"
                    elif sym.init_val is not None:
                        val = str(sym.init_val).strip()
                        if base == "integer":
                            default = str(int(val)) if val.lstrip("-+").isdigit() else "0"
                        elif base == "decimal":
                            default = f"Decimal('{val}')"
                        elif base == "boolean":
                            default = str(val.upper() in ("TRUE", "1", "YES", "T"))
                        elif base == "date":
                            if val.upper() in ("*DATX", "*DATN"):
                                default = "date.today()"
                            elif val.startswith("D'") and val.endswith("'"):
                                date_str = val[2:-1].strip()
                                default = f"datetime.strptime('{date_str}', '%m/%d/%Y').date()"
                            else:
                                default = "date.today()"
                        else:
                            default = repr(val.strip("'\""))
                    elif base == "decimal":
                        default = "Decimal('0')"
                    elif base == "date":
                        default = "date.today()"
                    elif base == "integer":
                        default = "0"
                    elif base == "boolean":
                        default = "False"
                    else:
                        default = '""'
                    self.emit_line(f"self.{py_name} = {default}")
                if not independent_syms:
                    self.emit_line("pass")
            self.emit_line("")

            for r_sym in sorted(redefined_syms, key=lambda s: s.redefine_offset):
                prop_name = self.ctx.clean_name(r_sym.name)
                parent_id = r_sym.redefine_parent
                parent_name = self.ctx.clean_name(parent_id.split(".")[-1])
                start_off = r_sym.redefine_offset
                length = r_sym.semantic_type.precision or r_sym.semantic_type.length or 2
                end_off = start_off + length

                self.emit_line("@property")
                self.emit_line(f"def {prop_name}(self) -> int:")
                with self.ctx.indent():
                    self.emit_line(f"sub = self.{parent_name}[{start_off}:{end_off}]")
                    self.emit_line("return int(sub) if sub.isdigit() else 0")
                self.emit_line("")

                self.emit_line(f"@{prop_name}.setter")
                self.emit_line(f"def {prop_name}(self, val: int):")
                with self.ctx.indent():
                    self.emit_line("val_str = f'{int(val):0" + str(length) + "d}'")
                    self.emit_line(
                        f"self.{parent_name} = self.{parent_name}[:{start_off}] + val_str + self.{parent_name}[{end_off}:]"
                    )
                self.emit_line("")

        for sub_name, sub_block in self.module.subroutines.items():
            sub_func = f"sub_{self.ctx.clean_name(sub_name)}"
            self.emit_line(f"def {sub_func}(ctx: {class_name}, session):")
            with self.ctx.indent():
                if sub_block.on_error:
                    self.emit_line("try:")
                    with self.ctx.indent():
                        if not sub_block.operations:
                            self.emit_line("pass")
                        for op in sub_block.operations:
                            self.emit_operation(op)
                    self.emit_line("except Exception as natural_err:")
                    with self.ctx.indent():
                        if not sub_block.on_error.body:
                            self.emit_line("pass")
                        for op in sub_block.on_error.body:
                            self.emit_operation(op)
                else:
                    for op in sub_block.operations:
                        self.emit_operation(op)
                    if not sub_block.operations:
                        self.emit_line("pass")
                self.emit_line("return ctx")
            self.emit_line("")

        func_name = f"execute_{self.ctx.clean_name(self.module.module_id)}"
        self.emit_line(f"def {func_name}(ctx: {class_name}, session):")
        with self.ctx.indent():
            on_error_op = next((op for op in self.module.operations if isinstance(op, OnErrorOp)), None)
            other_ops = [op for op in self.module.operations if not isinstance(op, OnErrorOp)]

            if on_error_op:
                self.emit_line("try:")
                with self.ctx.indent():
                    if not other_ops:
                        self.emit_line("pass")
                    for op in other_ops:
                        self.emit_operation(op)
                self.emit_line("except Exception as natural_err:")
                with self.ctx.indent():
                    if not on_error_op.body:
                        self.emit_line("pass")
                    for op in on_error_op.body:
                        self.emit_operation(op)
            else:
                for op in other_ops:
                    self.emit_operation(op)
                if not other_ops:
                    self.emit_line("pass")

            self.emit_line("return ctx")

        if emit_main:
            self.emit_main_block(class_name, func_name)

        return "\n".join(self.ctx.lines)
