# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
#
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
        # Prevent collisions with Python keywords in the column names
        if clean == "class":
            return "class_"
        return clean

    def emit_line(self, line: str, indent_level: int = 0):
        indent = "    " * indent_level
        self.lines.append(f"{indent}{line}")

    def generate(self) -> str:
        self.emit_line("from sqlalchemy import Column, String, Numeric, Integer, Boolean")
        self.emit_line("from sqlalchemy.orm import declarative_base")
        self.emit_line("")
        self.emit_line("Base = declarative_base()")
        self.emit_line("")

        # Ensure we sort the DDMs to guarantee deterministic file generation
        for ddm in sorted(self.ddms, key=lambda d: d.name):
            class_name = self._clean_name(ddm.name).replace("_view", "").title().replace("_", "")
            table_name = self._clean_name(ddm.name).replace("_view", "")

            self.emit_line(f"class {class_name}(Base):")
            self.emit_line(f"__tablename__ = '{table_name}'", 1)
            self.emit_line("")

            for i, field in enumerate(ddm.inline_fields):
                col_name = self._clean_name(field.name)
                kind = field.format.kind
                raw_spec = field.format.raw_spec

                # Extract digits and constraints from Natural format
                if kind == "alphanumeric":
                    # e.g., A4 -> length 4
                    length = ''.join(filter(str.isdigit, raw_spec))
                    length = length if length else "255"
                    sa_type = f"String({length})"
                elif kind in ("packed_decimal", "numeric"):
                    # e.g., P7.2 -> precision 7, scale 2
                    parts = raw_spec[1:].split('.')
                    prec = parts[0] if parts[0].isdigit() else "10"
                    scale = parts[1] if len(parts) > 1 else "0"
                    sa_type = f"Numeric({prec}, {scale})"
                elif kind in ("integer", "binary"):
                    sa_type = "Integer"
                elif kind == "boolean":
                    sa_type = "Boolean"
                else:
                    sa_type = "String"

                # Assume the first column parsed in the DDM is the Primary Key for basic models
                pk_arg = ", primary_key=True" if i == 0 else ""

                # The first arg is the actual target DB column name, the left hand is the Python access name
                self.emit_line(f"{col_name} = Column('{field.name.lower()}', {sa_type}{pk_arg})", 1)

            self.emit_line("")

        return "\n".join(self.lines)
