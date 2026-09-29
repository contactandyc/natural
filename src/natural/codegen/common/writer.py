# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from contextlib import contextmanager
from typing import List


class CodeWriter:
    """Manages string line buffers and scoped indentation levels."""

    def __init__(self, indent_str: str = "    "):
        self.lines: List[str] = []
        self.indent_level: int = 0
        self.indent_str: str = indent_str

    def emit_line(self, line: str = "", indent_offset: int = 0) -> None:
        if not line:
            self.lines.append("")
        else:
            level = max(0, self.indent_level + indent_offset)
            indent = self.indent_str * level
            self.lines.append(f"{indent}{line}")

    @contextmanager
    def indent(self, levels: int = 1):
        self.indent_level += levels
        try:
            yield
        finally:
            self.indent_level -= levels

    def get_code(self) -> str:
        return "\n".join(self.lines)
