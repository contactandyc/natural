# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
#
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import re
from pathlib import Path
from natural.ir.models import DataAreaRef, DataField, FieldFormat, ScopeType
from natural.normalizer.parser import NaturalParser

class Workspace:
    def __init__(self, include_dirs: list[Path]):
        self.include_dirs = include_dirs
        self.parser = NaturalParser()
        self._cache = {}

    def _read_file(self, name: str, exts: list[str]) -> str | None:
        """Finds and reads the first matching file in the include directories (case-insensitive)."""
        for d in self.include_dirs:
            for ext in exts:
                # Check uppercase name (TARIFF-P.nsa)
                p = d / f"{name}{ext}"
                if p.exists():
                    return p.read_text(encoding='utf-8')

                # Check lowercase name (tariff-p.nsa)
                p_lower = d / f"{name.lower()}{ext}"
                if p_lower.exists():
                    return p_lower.read_text(encoding='utf-8')
        return None

    def get_data_area(self, name: str, scope: ScopeType | None) -> DataAreaRef | None:
        """Loads and parses a Natural data area (.nsa, .nsl, .nsg)."""
        # Safely handle scope=None
        scope_prefix = f"{scope.value}_" if scope else ""
        cache_key = f"{scope_prefix}{name}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        content = self._read_file(name, ['.nsa', '.nsl', '.nsg', '.nsp', '.txt'])
        if not content:
            return None

        # Wrap raw field lines if missing the DEFINE DATA block
        if "DEFINE DATA" not in content.upper():
            # Default to LOCAL if no scope is provided and the block is missing
            scope_keyword = scope.value if scope else "LOCAL"
            content = f"DEFINE DATA\n{scope_keyword} USING {name}\nLOCAL\n{content}\nEND-DEFINE\nEND"

        try:
            ir0 = self.parser.parse(content, module_name=name)
            for area in ir0.data_areas:
                if area.inline_fields:
                    area.name = name
                    # If we parsed an implicit scope, update it
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
        # Matches typical DDM rows: "  1 AC RATE                              P  7.2  N N"
        pattern = re.compile(r'^\s*(\d+)\s+[A-Z0-9]{2}\s+([A-Z0-9\-]+)\s+([A-Z])\s+([\d\.]+)')

        for line in content.splitlines():
            match = pattern.match(line)
            if match:
                level = int(match.group(1))
                fname = match.group(2)
                kind_char = match.group(3)
                raw_spec = f"{kind_char}{match.group(4)}"

                kind_map = {
                    "A": "alphanumeric", "P": "packed_decimal",
                    "N": "numeric", "I": "integer",
                    "B": "binary", "L": "boolean"
                }
                kind = kind_map.get(kind_char, "unknown")

                fields.append(DataField(
                    level=level, name=fname,
                    format=FieldFormat(kind=kind, raw_spec=raw_spec)
                ))

        if fields:
            area = DataAreaRef(name=name, scope=ScopeType.LOCAL, inline_fields=fields)
            self._cache[cache_key] = area
            return area
        return None
