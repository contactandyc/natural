# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import List
from natural.ir.models import DataAreaRef


class ORMEmitter:
    def __init__(self, ddms: List[DataAreaRef]):
        self.ddms = ddms
        self.lines: List[str] = []

    def _clean_name(self, name: str) -> str:
        """Converts COBOL/Natural style names (CLASS) to Pythonic ones (class_)."""
        clean = name.replace("#", "").replace("-", "_").lower()
        if clean == "class":
            return "class_"
        return clean

    def emit_line(self, line: str, indent_level: int = 0):
        indent = "    " * indent_level
        self.lines.append(f"{indent}{line}")

    def generate(self) -> str:
        self.emit_line("from decimal import Decimal")
        self.emit_line("from sqlalchemy import Column, String, Numeric, Integer, Boolean, JSON")
        self.emit_line("from sqlalchemy.orm import declarative_base")
        self.emit_line("")
        self.emit_line("Base = declarative_base()")
        self.emit_line("")

        for ddm in sorted(self.ddms, key=lambda d: d.name):
            class_name = self._clean_name(ddm.name).replace("_view", "").title().replace("_", "")
            table_name = self._clean_name(ddm.name).replace("_view", "")

            self.emit_line(f"class {class_name}(Base):")
            self.emit_line(f"__tablename__ = '{table_name}'", 1)
            self.emit_line("")

            for i, field in enumerate(ddm.inline_fields):
                if field.level > 1 and getattr(field, "parent_name", None):
                    continue

                col_name = self._clean_name(field.name)
                kind = field.format.kind if field.format else "unknown"
                raw_spec = field.format.raw_spec if field.format else ""

                if getattr(field, "is_multiple", False) or getattr(field, "is_periodic", False) or getattr(field, "array_dim", None):
                    dim = int(field.array_dim) if (field.array_dim and field.array_dim.isdigit()) else getattr(field, "max_index", 1)
                    if kind == "alphanumeric":
                        default_expr = f'lambda: ["" for _ in range({dim})]'
                    elif kind in ("packed_decimal", "numeric"):
                        default_expr = f'lambda: [Decimal(\'0\') for _ in range({dim})]'
                    elif kind in ("integer", "binary"):
                        default_expr = f'lambda: [0 for _ in range({dim})]'
                    else:
                        default_expr = f'lambda: [None for _ in range({dim})]'
                    pk_arg = ", primary_key=True" if i == 0 else ""
                    self.emit_line(f"{col_name} = Column('{field.name.lower()}', JSON, default={default_expr}{pk_arg})", 1)
                elif kind == "alphanumeric":
                    length = ''.join(filter(str.isdigit, raw_spec))
                    length = length if length else "255"
                    sa_type = f"String({length})"
                    pk_arg = ", primary_key=True" if i == 0 else ""
                    self.emit_line(f"{col_name} = Column('{field.name.lower()}', {sa_type}{pk_arg})", 1)
                elif kind in ("packed_decimal", "numeric"):
                    parts = raw_spec[1:].split('.')
                    prec = parts[0] if parts[0].isdigit() else "10"
                    scale = parts[1] if len(parts) > 1 else "0"
                    sa_type = f"Numeric({prec}, {scale})"
                    pk_arg = ", primary_key=True" if i == 0 else ""
                    self.emit_line(f"{col_name} = Column('{field.name.lower()}', {sa_type}{pk_arg})", 1)
                elif kind in ("integer", "binary"):
                    pk_arg = ", primary_key=True" if i == 0 else ""
                    self.emit_line(f"{col_name} = Column('{field.name.lower()}', Integer{pk_arg})", 1)
                elif kind == "boolean":
                    pk_arg = ", primary_key=True" if i == 0 else ""
                    self.emit_line(f"{col_name} = Column('{field.name.lower()}', Boolean{pk_arg})", 1)
                else:
                    pk_arg = ", primary_key=True" if i == 0 else ""
                    self.emit_line(f"{col_name} = Column('{field.name.lower()}', String{pk_arg})", 1)

            self.emit_line("")

        return "\n".join(self.lines)
