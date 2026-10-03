# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import re
from typing import List
from natural.ir.models import (
    DataAreaRef,
    DataField,
    FieldFormat,
    RedefineDefinition,
    ScopeType,
    ViewDefinition,
    ViewField,
)


class DataBlockParser:
    def __init__(self):
        self.field_pattern = re.compile(
            r"^\s*(\d{1,2})\s+([*#\+A-Za-z0-9\-_]+)(?:\s*\(([^)]+)\))?(?:\s*\(([^)]+)\))?(?:\s+DYNAMIC)?(?:\s+INIT\s*<?([^>]+)?>?)?\s*$",
            re.IGNORECASE,
        )
        self.redefine_pattern = re.compile(
            r"^\s*(\d{1,2})\s+REDEFINE\s+([*#\+A-Za-z0-9\-_]+)\s*$",
            re.IGNORECASE,
        )
        self.using_pattern = re.compile(
            r"^\s*(LOCAL|PARAMETER|GLOBAL)\s+USING\s+([A-Za-z0-9\-_]+)\s*$",
            re.IGNORECASE,
        )
        self.view_pattern = re.compile(
            r"^\s*(\d{1,2})\s+([A-Za-z0-9\-_]+)\s+VIEW\s+(?:OF\s+)?([A-Za-z0-9\-_]+)\s*$",
            re.IGNORECASE,
        )
        self.view_field_pattern = re.compile(
            r"^\s*02\s+([A-Za-z0-9\-_]+)(?:\s*\(([^)]+)\))?\s*$",
            re.IGNORECASE,
        )

    def parse(self, raw_content: str) -> List[DataAreaRef]:
        areas: List[DataAreaRef] = []
        current_area: DataAreaRef | None = None
        current_scope = ScopeType.LOCAL
        current_redefine_target: str | None = None
        current_group: str | None = None
        current_view: ViewDefinition | None = None

        clean_text = re.sub(r"/\*(?!\s*\)).*?(?:\*/|$)", "", raw_content, flags=re.MULTILINE)
        clean_text = re.sub(r"(?<=[^\n])\s+(\d{1,2}\s+(?:REDEFINE|[#*A-Za-z]))", r"\n\1", clean_text)
        lines = [line.strip() for line in clean_text.splitlines() if line.strip() and not line.strip().startswith("*")]

        for line in lines:
            if line.upper() in ("LOCAL", "PARAMETER", "GLOBAL"):
                current_scope = ScopeType(line.upper())
                current_area = DataAreaRef(name=f"INLINE_{current_scope.value}", scope=current_scope)
                areas.append(current_area)
                current_view = None
                current_redefine_target = None
                current_group = None
                continue

            using_match = self.using_pattern.match(line)
            if using_match:
                scope_str, name = using_match.groups()
                areas.append(DataAreaRef(name=name.upper(), scope=ScopeType(scope_str.upper())))
                current_view = None
                current_redefine_target = None
                current_group = None
                continue

            if not current_area:
                current_area = DataAreaRef(name=f"INLINE_{current_scope.value}", scope=current_scope)
                areas.append(current_area)

            view_match = self.view_pattern.match(line)
            if view_match:
                level = int(view_match.group(1))
                view_name = view_match.group(2).upper()
                ddm_name = view_match.group(3).upper()
                current_view = ViewDefinition(level=level, view_name=view_name, ddm_name=ddm_name, fields=[])
                current_area.views.append(current_view)
                current_redefine_target = None
                current_group = None
                continue

            if current_view and line.startswith("02"):
                vf_match = self.view_field_pattern.match(line)
                if vf_match:
                    f_name = vf_match.group(1).upper()
                    dim = vf_match.group(2)
                    current_view.fields.append(ViewField(level=2, name=f_name, array_dim=dim))
                    continue

            redef_match = self.redefine_pattern.match(line)
            if redef_match:
                level = int(redef_match.group(1))
                target = redef_match.group(2)
                current_redefine_target = target
                current_group = None
                current_area.redefines.append(RedefineDefinition(level=level, target_name=target))
                current_view = None
                continue

            field_match = self.field_pattern.match(line)
            if field_match:
                level = int(field_match.group(1))
                name = field_match.group(2)
                raw_format = field_match.group(3)
                second_paren = field_match.group(4)
                init_val = field_match.group(5)

                if level == 1:
                    current_redefine_target = None
                    current_view = None
                    if not raw_format:
                        current_group = name
                    else:
                        current_group = None

                array_dim = None
                dim_start = 1
                dim_end = None

                if second_paren:
                    array_dim = second_paren.strip()
                elif raw_format and "/" in raw_format:
                    fmt_part, dim_part = raw_format.split("/", 1)
                    raw_format = fmt_part.strip()
                    array_dim = dim_part.strip()
                elif "DYNAMIC" in line.upper() and not array_dim:
                    array_dim = "*"

                if array_dim:
                    if ":" in array_dim:
                        parts = array_dim.split(":", 1)
                        if parts[0].strip().isdigit() and parts[1].strip().isdigit():
                            dim_start = int(parts[0].strip())
                            dim_end = int(parts[1].strip())
                    elif array_dim.isdigit():
                        dim_start = 1
                        dim_end = int(array_dim)

                fmt = self._parse_format(raw_format.strip()) if raw_format else None

                field = DataField(
                    level=level,
                    name=name,
                    format=fmt,
                    array_dim=array_dim,
                    max_index=dim_end or 1,
                    dim_start=dim_start,
                    dim_end=dim_end,
                    init_val=init_val.strip() if init_val else None,
                    parent_name=current_redefine_target if (level > 1 and current_redefine_target) else None,
                    group_name=current_group if (level > 1 and not current_redefine_target) else None,
                )
                current_area.inline_fields.append(field)

        return areas

    def _parse_format(self, raw_fmt: str) -> FieldFormat:
        if not raw_fmt:
            return FieldFormat(kind="unknown", raw_spec="")

        clean_spec = raw_fmt.upper().replace("DYNAMIC", "").strip()
        if "/" in clean_spec:
            clean_spec = clean_spec.split("/", 1)[0].strip()

        kind_char = clean_spec[0] if clean_spec else "A"
        kind_map = {
            "A": "alphanumeric",
            "P": "packed_decimal",
            "N": "numeric",
            "I": "integer",
            "B": "binary",
            "L": "boolean",
            "D": "date",
        }
        kind = kind_map.get(kind_char, "unknown")
        fmt = FieldFormat(kind=kind, raw_spec=raw_fmt)

        match = re.match(r"^[A-Z](\d*)(?:\.(\d+))?$", clean_spec, re.IGNORECASE)
        if match:
            if match.group(1):
                fmt.length = int(match.group(1))
                fmt.digits = int(match.group(1))
            if match.group(2):
                fmt.decimals = int(match.group(2))
        return fmt
