# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import Dict, List, Optional
from natural.codegen.common import CodeWriter, clean_func_name, clean_name, to_pascal_case
from natural.ir.semantic import SemanticModule, SemanticType, Symbol


class EmitterContext:
    """Maintains active loop views, symbol metadata, and naming resolutions for emission."""

    def __init__(self, module: SemanticModule, writer: Optional[CodeWriter] = None):
        self.module = module
        self.writer = writer or CodeWriter()
        self._sym_by_id: Dict[str, Symbol] = {s.id: s for s in module.symbols.values()}
        self.current_loop_views: List[str] = []

    @property
    def lines(self) -> List[str]:
        return self.writer.lines

    @property
    def indent_level(self) -> int:
        return self.writer.indent_level

    @indent_level.setter
    def indent_level(self, val: int):
        self.writer.indent_level = val

    def emit_line(self, line: str = "", indent_offset: int = 0) -> None:
        self.writer.emit_line(line, indent_offset=indent_offset)

    def indent(self, levels: int = 1):
        return self.writer.indent(levels=levels)

    def get_symbol(self, symbol_id: str) -> Optional[Symbol]:
        return self._sym_by_id.get(symbol_id)

    def clean_name(self, name: str) -> str:
        return clean_name(name)

    def clean_func_name(self, name: str) -> str:
        return clean_func_name(name)

    def to_pascal_case(self, name: str) -> str:
        return to_pascal_case(name)

    def resolve_ref(self, symbol_id: str, model_class: Optional[str] = None) -> str:
        if symbol_id.startswith("record."):
            return symbol_id
        parts = symbol_id.split(".")
        if len(parts) >= 3 and parts[0] == "fn":
            return self.clean_name(parts[-1])
        if len(parts) >= 3 and parts[1] in ("local", "parameter"):
            return f"ctx.{self.clean_name(parts[-1])}"
        elif len(parts) >= 3 and parts[1] == "entity":
            col_name = self.clean_name(parts[-1])
            view_or_entity = self.clean_name(parts[2]) if len(parts) >= 4 else ""

            is_active_loop = (
                    view_or_entity in ("active", "")
                    or (bool(self.current_loop_views) and view_or_entity in self.current_loop_views)
            )

            if model_class:
                if is_active_loop:
                    return f"{model_class}.{col_name}"
                return f"{view_or_entity}_record.{col_name}"

            if is_active_loop:
                return f"record.{col_name}"
            return f"{view_or_entity}_record.{col_name}"
        elif len(parts) >= 3 and parts[1] == "unresolved":
            return f"ctx.{self.clean_name(parts[-1])}_UNRESOLVED"
        return symbol_id

    def type_to_python_hint(self, sem_type: SemanticType) -> str:
        base = sem_type.base
        if base == "decimal":
            return "Decimal"
        elif base == "integer":
            return "int"
        elif base == "string":
            return "str"
        elif base == "boolean":
            return "bool"
        elif base == "date":
            return "date"
        return "Any"
