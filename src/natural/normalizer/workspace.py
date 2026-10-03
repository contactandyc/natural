# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import re
from pathlib import Path
from typing import List, Optional
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
                    return p.read_text(encoding="utf-8")

                p_lower = d / f"{name.lower()}{ext}"
                if p_lower.exists():
                    return p_lower.read_text(encoding="utf-8")
        return None

    def get_data_area(self, name: str, scope: ScopeType | None) -> DataAreaRef | None:
        """Loads and parses a Natural data area (.nsa, .nsl, .nsg)."""
        scope_prefix = f"{scope.value}_" if scope else ""
        cache_key = f"{scope_prefix}{name}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        content = self._read_file(name, [".nsa", ".nsl", ".nsg", ".nsp", ".txt"])
        if not content:
            return None

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

    def get_subprogram_parameters(self, name: str) -> List[DataField]:
        """Extracts ordered parameter definitions from a target .nsn subprogram or .nsp program."""
        clean_name = name.upper().replace(".NSN", "").replace(".NSP", "")
        cache_key = f"PARAMS_{clean_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        content = self._read_file(clean_name, [".nsn", ".nsp", ".txt", ".nsa"])
        if not content:
            return []

        try:
            from natural.normalizer.pass1_parser import Pass1Parser
            from natural.normalizer.pass2_dispatcher import Pass2Dispatcher

            p1 = Pass1Parser(self)
            dispatcher = Pass2Dispatcher()

            pass1_ast = p1.parse(content, module_name=clean_name)
            ir0 = dispatcher.lower_module(pass1_ast)

            params: List[DataField] = []
            for area in ir0.data_areas:
                if area.scope == ScopeType.PARAMETER:
                    fields = area.inline_fields
                    if not fields:
                        ext_area = self.get_data_area(area.name, ScopeType.PARAMETER)
                        if ext_area:
                            fields = ext_area.inline_fields
                    for f in fields:
                        if f.format:
                            params.append(f)

            self._cache[cache_key] = params
            return params
        except Exception:
            return []

    def get_ddm(self, name: str) -> DataAreaRef | None:
        """Loads and parses a tabular Adabas Data Definition Module (.ddm)."""
        cache_key = f"DDM_{name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        content = self._read_file(name, [".ddm", ".txt"])
        if not content:
            return None

        fields = []
        pe_pattern = re.compile(
            r"^\s*(\d+)\s+(PE|GR)\s+([A-Z0-9\-]+)(?:\s*\(([0-9\:]+)\))?.*$",
            re.IGNORECASE,
        )
        pattern = re.compile(
            r"^\s*(\d+)\s+([A-Z0-9]{2})\s+([A-Z0-9\-]+)\s+([A-Z])\s+([\d\.]+)(.*)$"
        )

        current_pe_group: Optional[str] = None

        for line in content.splitlines():
            pe_match = pe_pattern.match(line)
            if pe_match:
                level = int(pe_match.group(1))
                fname = pe_match.group(3)
                dim_spec = pe_match.group(4)
                dim_start = None
                dim_end = None
                max_idx = 1
                if dim_spec:
                    if ":" in dim_spec:
                        parts = dim_spec.split(":")
                        if parts[0].isdigit() and parts[1].isdigit():
                            dim_start = int(parts[0])
                            dim_end = int(parts[1])
                    elif dim_spec.isdigit():
                        dim_start = 1
                        dim_end = int(dim_spec)
                    max_idx = dim_end or 1

                if level == 1:
                    current_pe_group = fname

                fields.append(
                    DataField(
                        level=level,
                        name=fname,
                        format=FieldFormat(kind="periodic_group", raw_spec="PE"),
                        is_periodic=True,
                        array_dim=str(max_idx) if dim_spec else None,
                        max_index=max_idx,
                        dim_start=dim_start or 1,
                        dim_end=dim_end,
                    )
                )
                continue

            match = pattern.match(line)
            if match:
                level = int(match.group(1))
                code = match.group(2)
                fname = match.group(3)
                kind_char = match.group(4)
                val_spec = match.group(5)
                raw_spec = f"{kind_char}{val_spec}"
                remainder = match.group(6)

                if level == 1:
                    current_pe_group = None

                kind_map = {
                    "A": "alphanumeric",
                    "P": "packed_decimal",
                    "N": "numeric",
                    "I": "integer",
                    "B": "binary",
                    "L": "boolean",
                }
                kind = kind_map.get(kind_char, "unknown")

                digits = None
                decimals = None
                length = None
                if "." in val_spec:
                    p_parts = val_spec.split(".", 1)
                    if p_parts[0].isdigit():
                        digits = int(p_parts[0])
                    if p_parts[1].isdigit():
                        decimals = int(p_parts[1])
                elif val_spec.isdigit():
                    length = int(val_spec)
                    digits = int(val_spec)

                fmt = FieldFormat(
                    kind=kind,
                    raw_spec=raw_spec,
                    length=length,
                    digits=digits,
                    decimals=decimals,
                )

                has_nested_parens = bool(re.search(r"\([^)]*\([^)]*\)", remainder))

                sub_fields = []
                array_dim = None
                max_index = 1
                dim_start = 1
                dim_end = None
                is_multiple = False

                if has_nested_parens:
                    raw_subs = re.findall(
                        r"([A-Za-z0-9\-_]+)\s*\(\s*(\d+)\s*:\s*(\d+)\s*\)",
                        remainder,
                    )
                    for s_name, s_start, s_end in raw_subs:
                        sub_fields.append((s_name, int(s_start), int(s_end)))
                elif "(" in remainder:
                    range_m = re.search(r"\(\s*(?:(\d+)\s*:\s*)?(\d+)\s*\)", remainder)
                    if range_m:
                        if range_m.group(1):
                            dim_start = int(range_m.group(1))
                            dim_end = int(range_m.group(2))
                        else:
                            dim_start = 1
                            dim_end = int(range_m.group(2))
                        max_index = dim_end
                        array_dim = str(dim_end)
                        is_multiple = True

                parent_name = current_pe_group if (level > 1 and current_pe_group) else None

                is_super = code.upper() == "SP" or bool(re.search(r"\bSP\b", remainder)) or (bool(sub_fields) and len(sub_fields) > 1)
                is_sub = code.upper() == "SB" or bool(re.search(r"\bSB\b", remainder)) or (bool(sub_fields) and len(sub_fields) == 1)
                is_uniq = bool(re.search(r"\b(U|UQ)\b", remainder))
                is_desc = is_super or is_sub or is_uniq or bool(re.search(r"\b(D|DE)\b", remainder))

                fields.append(
                    DataField(
                        level=level,
                        name=fname,
                        format=fmt,
                        sub_fields=sub_fields,
                        array_dim=array_dim,
                        max_index=max_index,
                        dim_start=dim_start,
                        dim_end=dim_end,
                        is_multiple=is_multiple,
                        is_descriptor=is_desc,
                        is_unique=is_uniq,
                        is_subdescriptor=is_sub,
                        is_superdescriptor=is_super,
                        parent_name=parent_name,
                    )
                )

        if fields:
            area = DataAreaRef(name=name, scope=ScopeType.LOCAL, inline_fields=fields)
            self._cache[cache_key] = area
            return area
        return None
