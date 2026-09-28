# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import re
from pathlib import Path
from natural.ir.models import DataAreaRef, DataField, FieldFormat, ScopeType


class Workspace:
    def __init__(self, include_dirs: list[Path]):
        self.include_dirs = include_dirs
        self._cache = {}

    def _read_file(self, name: str, exts: list[str]) -> str | None:
        """Finds and reads the first matching file in the include directories (case-insensitive)."""
        for d in self.include_dirs:
            for ext in exts:
                p = d / f"{name}{ext}"
                if p.exists():
                    return p.read_text(encoding='utf-8')

                p_lower = d / f"{name.lower()}{ext}"
                if p_lower.exists():
                    return p_lower.read_text(encoding='utf-8')
        return None

    def get_data_area(self, name: str, scope: ScopeType | None) -> DataAreaRef | None:
        """Loads and parses a Natural data area (.nsa, .nsl, .nsg)."""
        scope_prefix = f"{scope.value}_" if scope else ""
        cache_key = f"{scope_prefix}{name}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        content = self._read_file(name, ['.nsa', '.nsl', '.nsg', '.nsp', '.txt'])
        if not content:
            return None

        # Wrap raw field lines if missing the DEFINE DATA block
        if "DEFINE DATA" not in content.upper():
            scope_keyword = scope.value if scope else "LOCAL"
            content = f"DEFINE DATA\n{scope_keyword} USING {name}\nLOCAL\n{content}\nEND-DEFINE\nEND"

        try:
            from natural.normalizer.pass1_parser import Pass1Parser
            from natural.normalizer.pass2_dispatcher import Pass2Dispatcher

            p1 = Pass1Parser(self)
            dispatcher = Pass2Dispatcher()

            pass1_ast = p1.parse(content, module_name=name)
            ir0 = dispatcher.lower_module(pass1_ast)

            for area in ir0.data_areas:
                if area.inline_fields:
                    area.name = name
                    if scope:
                        area.scope = scope
                    self._cache[cache_key] = area
                    return area
        except Exception as e:
            print(f"Warning: Failed to parse data area {name}: {e}")
        return None

    def get_ddm(self, name: str) -> DataAreaRef | None:
        """Loads and parses a tabular Adabas Data Definition Module (.ddm)."""
        cache_key = f"DDM_{name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        content = self._read_file(name, ['.ddm', '.txt'])
        if not content:
            return None

        fields = []
        pattern = re.compile(r'^\s*(\d+)\s+([A-Z0-9]{2})\s+([A-Z0-9\-]+)\s+([A-Z])\s+([\d\.]+)(.*)$')

        for line in content.splitlines():
            match = pattern.match(line)
            if match:
                level = int(match.group(1))
                code = match.group(2)
                fname = match.group(3)
                kind_char = match.group(4)
                raw_spec = f"{kind_char}{match.group(5)}"
                remainder = match.group(6)

                kind_map = {
                    "A": "alphanumeric", "P": "packed_decimal",
                    "N": "numeric", "I": "integer",
                    "B": "binary", "L": "boolean"
                }
                kind = kind_map.get(kind_char, "unknown")

                sub_fields = []
                if "(" in remainder:
                    raw_subs = re.findall(r'([A-Za-z0-9\-_]+)\s*\(\s*(\d+)\s*:\s*(\d+)\s*\)', remainder)
                    for s_name, s_start, s_end in raw_subs:
                        sub_fields.append((s_name, int(s_start), int(s_end)))

                fields.append(DataField(
                    level=level, name=fname,
                    format=FieldFormat(kind=kind, raw_spec=raw_spec),
                    sub_fields=sub_fields,
                ))

        if fields:
            area = DataAreaRef(name=name, scope=ScopeType.LOCAL, inline_fields=fields)
            self._cache[cache_key] = area
            return area
        return None
