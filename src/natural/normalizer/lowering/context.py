# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import sys
from typing import Dict, List, Optional, Tuple
from natural.ir.models import DataAreaRef, NaturalModule, ScopeType, ViewDefinition
from natural.ir.semantic import SemanticType, Symbol
from natural.normalizer.workspace import Workspace


def normalize_fn_name(name: str) -> str:
    """Strips leading Natural function prefixes (FN_, F_, UDF_) and normalizes separators."""
    s = name.upper().replace("#", "_").replace("-", "_")
    while s.startswith(("FN_", "F_", "UDF_")):
        if s.startswith("FN_"):
            s = s[3:]
        elif s.startswith("F_"):
            s = s[2:]
        elif s.startswith("UDF_"):
            s = s[4:]
    return s.strip("_")


class ActiveLoopContext:
    def __init__(
            self,
            loop_id: str,
            label: Optional[str] = None,
            entity: Optional[str] = None,
            view_name: Optional[str] = None,
            is_histogram: bool = False,
    ):
        self.loop_id = loop_id
        self.label = label.upper() if label else None
        self.entity = entity
        self.view_name = view_name.upper() if view_name else None
        self.is_histogram = is_histogram


class LoweringContext:
    """Maintains symbol tables, loop frames, and workspace scope resolution during IR lowering."""

    def __init__(self, ast: NaturalModule, workspace: Optional[Workspace] = None):
        self.ast = ast
        self.workspace = workspace
        self.symbols: Dict[str, Symbol] = {}
        self.loop_stack: List[ActiveLoopContext] = []
        self.loop_counter: int = 0
        self.active_function_name: Optional[str] = None
        self.function_symbols: Dict[str, Symbol] = {}

    def push_loop(self, loop_ctx: ActiveLoopContext) -> None:
        self.loop_stack.append(loop_ctx)

    def pop_loop(self) -> Optional[ActiveLoopContext]:
        if self.loop_stack:
            return self.loop_stack.pop()
        return None

    def find_view_definition(self, view_name: Optional[str]) -> Optional[ViewDefinition]:
        if not view_name:
            return None
        v_upper = view_name.upper()
        for area in self.ast.data_areas:
            for v in area.views:
                if v.view_name.upper() == v_upper:
                    return v
        return None

    def parse_format(self, raw_fmt: str) -> SemanticType:
        if not raw_fmt:
            return SemanticType(base="unknown")
        raw_fmt = raw_fmt.strip("()")
        kind = raw_fmt[0]
        if kind in ("P", "N"):
            parts = raw_fmt[1:].split(".")
            prec = int(parts[0]) if parts[0].isdigit() else 0
            scale = int(parts[1]) if len(parts) > 1 else 0
            storage = "packed_decimal" if kind == "P" else "unpacked_decimal"
            return SemanticType(base="decimal", precision=prec, scale=scale, storage=storage)
        elif kind == "A":
            clean_len = raw_fmt[1:].replace("DYNAMIC", "").strip()
            if "/" in clean_len:
                clean_len = clean_len.split("/", 1)[0].strip()
            length = int(clean_len) if clean_len.isdigit() else 0
            return SemanticType(base="string", length=length, storage="alphanumeric")
        elif kind == "D":
            return SemanticType(base="date", length=8, storage="date")
        elif kind == "L":
            return SemanticType(base="boolean", length=1, storage="boolean")
        elif kind in ("I", "B"):
            length = int(raw_fmt[1:]) if raw_fmt[1:].isdigit() else 4
            return SemanticType(base="integer", length=length, storage="binary")
        return SemanticType(base="unknown", storage=raw_fmt)

    def _field_length(self, sem_type: SemanticType) -> int:
        if sem_type.base == "string" and sem_type.length:
            return sem_type.length
        elif sem_type.base == "decimal" and sem_type.precision:
            return sem_type.precision
        elif sem_type.base == "integer":
            return sem_type.length or 4
        elif sem_type.base == "date":
            return sem_type.length or 8
        elif sem_type.base == "boolean":
            return 1
        return sem_type.length or sem_type.precision or 1

    def build_symbol_table(self) -> None:
        redefine_offsets: Dict[str, int] = {}

        for area in self.ast.data_areas:
            fields = area.inline_fields

            if not fields and self.workspace:
                ext_area = self.workspace.get_data_area(area.name, area.scope)
                if ext_area:
                    fields = ext_area.inline_fields
                else:
                    print(
                        f"[Compiler Warning] Unable to resolve {area.scope.value} USING {area.name}.",
                        file=sys.stderr,
                    )

            for field in fields:
                clean_name = field.name.lower().replace("#", "")
                sym_id = f"sym.{area.scope.value.lower()}.{clean_name}"
                raw_spec = field.format.raw_spec if field.format else "A"
                sem_type = self.parse_format(raw_spec)

                parent_id = None
                offset = 0
                if field.parent_name:
                    parent_clean = field.parent_name.lower().replace("#", "")
                    parent_id = f"sym.{area.scope.value.lower()}.{parent_clean}"
                    offset = redefine_offsets.get(parent_id, 0)
                    redefine_offsets[parent_id] = offset + self._field_length(sem_type)

                is_arr = bool(field.array_dim or getattr(field, "is_periodic", False) or getattr(field, "is_multiple", False))

                sym = Symbol(
                    id=sym_id,
                    name=field.name,
                    scope=area.scope.value.lower(),
                    semantic_type=sem_type,
                    redefine_parent=parent_id,
                    redefine_offset=offset,
                    is_array=is_arr,
                    init_val=field.init_val,
                )
                self.symbols[field.name] = sym

                if field.parent_name:
                    qualified = f"{field.parent_name}.{field.name}"
                    self.symbols[qualified] = sym

                if getattr(field, "group_name", None):
                    qualified_grp = f"{field.group_name}.{field.name}"
                    self.symbols[qualified_grp] = sym

            for v_def in area.views:
                v_name = v_def.view_name
                v_clean = v_name.lower().replace("#", "")
                ddm_name = v_def.ddm_name or v_name
                ddm = self.workspace.get_ddm(ddm_name) if self.workspace else None
                ddm_fields_by_name = {f.name.upper(): f for f in ddm.inline_fields} if ddm else {}

                for vf in v_def.fields:
                    f_name = vf.name
                    f_clean = f_name.lower().replace("#", "")
                    sym_id = f"sym.entity.{v_clean}.{f_clean}"

                    matched_ddm_f = ddm_fields_by_name.get(f_name.upper())
                    if matched_ddm_f and matched_ddm_f.format:
                        sem_type = self.parse_format(matched_ddm_f.format.raw_spec)
                        is_arr = bool(matched_ddm_f.array_dim or getattr(matched_ddm_f, "is_periodic", False) or getattr(matched_ddm_f, "is_multiple", False))
                    else:
                        sem_type = SemanticType(base="string")
                        is_arr = bool(vf.array_dim)

                    sym = Symbol(
                        id=sym_id,
                        name=f_name,
                        scope="entity_field",
                        semantic_type=sem_type,
                        is_array=is_arr,
                    )
                    self.symbols[f"{v_name}.{f_name}"] = sym

    def resolve_ref(self, name: str) -> str:
        if self.active_function_name:
            if name in self.function_symbols:
                return self.function_symbols[name].id
            clean_f = name.split(".")[-1].lower().replace("#", "")
            for s in self.function_symbols.values():
                if s.name.lower().replace("#", "") == clean_f:
                    return s.id

        if name in self.symbols:
            return self.symbols[name].id

        clean = name.split(".")[-1].lower().replace("#", "")

        for sym in self.symbols.values():
            if sym.name.lower().replace("#", "") == clean:
                return sym.id

        for ctx in reversed(self.loop_stack):
            if ctx.view_name:
                v_def = self.find_view_definition(ctx.view_name)
                if v_def:
                    for vf in v_def.fields:
                        if vf.name.lower().replace("#", "") == clean:
                            return f"sym.entity.{ctx.view_name.lower()}.{clean}"
                    if v_def.ddm_name and self.workspace:
                        ddm = self.workspace.get_ddm(v_def.ddm_name)
                        if ddm:
                            for f in ddm.inline_fields:
                                if f.name.lower().replace("#", "") == clean:
                                    return f"sym.entity.{ctx.view_name.lower()}.{clean}"

                if self.workspace:
                    ddm = self.workspace.get_ddm(ctx.view_name)
                    if ddm:
                        for f in ddm.inline_fields:
                            if f.name.lower() == clean:
                                return f"sym.entity.{ctx.view_name.lower()}.{clean}"

        if "." in name:
            parts = name.split(".")
            v_name, f_name = parts[0], parts[1]
            return f"sym.entity.{v_name.lower()}.{f_name.lower().replace('#', '')}"

        return f"sym.unresolved.{name.lower().replace('#', '').replace('.', '_')}"

    def get_fields_for_scope(self, scope_name: str) -> List[Tuple[str, str, str]]:
        raw_name = scope_name.upper().strip()
        clean_name = raw_name.replace("#", "").replace("-", "_")
        results: List[Tuple[str, str, str]] = []
        seen_norms = set()

        def add_field(orig_name: str, sym_id: str):
            norm = orig_name.lower().replace("#", "").replace("-", "_").split(".")[-1]
            if norm not in seen_norms:
                seen_norms.add(norm)
                results.append((norm, sym_id, orig_name))

        matched_loop_ctx = None
        for ctx in reversed(self.loop_stack):
            v_name = ctx.view_name.upper() if ctx.view_name else ""
            v_clean = v_name.replace("#", "").replace("-", "_")
            v_no_view = v_clean.replace("_VIEW", "")
            e_name = ctx.entity.upper() if ctx.entity else ""
            e_clean = e_name.replace("#", "").replace("-", "_")

            if raw_name in (v_name, e_name) or clean_name in (v_clean, v_no_view, e_clean):
                matched_loop_ctx = ctx
                break

        if matched_loop_ctx and matched_loop_ctx.view_name:
            view_n = matched_loop_ctx.view_name
            if self.workspace:
                ddm = self.workspace.get_ddm(view_n)
                if not ddm and view_n.endswith("-VIEW"):
                    ddm = self.workspace.get_ddm(view_n[:-5])
                if not ddm:
                    ddm = self.workspace.get_ddm(f"{view_n}-VIEW")
                if ddm:
                    for f in ddm.inline_fields:
                        clean_col = f.name.lower().replace("#", "")
                        sym_id = f"sym.entity.{view_n.lower()}.{clean_col}"
                        add_field(f.name, sym_id)

            if not results:
                for area in self.ast.data_areas:
                    for v in area.views:
                        if v.view_name.upper() == view_n.upper():
                            for f in v.fields:
                                clean_col = f.name.lower().replace("#", "")
                                sym_id = f"sym.entity.{view_n.lower()}.{clean_col}"
                                add_field(f.name, sym_id)

            if results:
                return results

        if self.workspace:
            ddm = self.workspace.get_ddm(raw_name)
            if not ddm and not raw_name.endswith("-VIEW"):
                ddm = self.workspace.get_ddm(f"{raw_name}-VIEW")
            if not ddm and raw_name.endswith("-VIEW"):
                ddm = self.workspace.get_ddm(raw_name[:-5])
            if ddm:
                for f in ddm.inline_fields:
                    clean_col = f.name.lower().replace("#", "")
                    sym_id = f"sym.entity.{ddm.name.lower()}.{clean_col}"
                    add_field(f.name, sym_id)
                if results:
                    return results

        for area in self.ast.data_areas:
            fields = list(area.inline_fields)
            if not fields and self.workspace:
                ext_area = self.workspace.get_data_area(area.name, area.scope)
                if ext_area:
                    fields = ext_area.inline_fields

            in_group = False
            for f in fields:
                f_raw = f.name.upper()
                f_clean = f_raw.replace("#", "").replace("-", "_")

                if getattr(f, "group_name", None):
                    grp_raw = f.group_name.upper()
                    grp_clean = grp_raw.replace("#", "").replace("-", "_")
                    if raw_name == grp_raw or clean_name == grp_clean:
                        clean_col = f.name.lower().replace("#", "")
                        sym_id = f"sym.{area.scope.value.lower()}.{clean_col}"
                        add_field(f.name, sym_id)
                elif f.level == 1:
                    if f_raw == raw_name or f_clean == clean_name:
                        in_group = True
                    else:
                        in_group = False
                elif in_group and f.level > 1:
                    clean_col = f.name.lower().replace("#", "")
                    sym_id = f"sym.{area.scope.value.lower()}.{clean_col}"
                    add_field(f.name, sym_id)

            if results:
                return results

        for area in self.ast.data_areas:
            area_raw = area.name.upper()
            area_clean = area_raw.replace("#", "").replace("-", "_")
            if raw_name == area_raw or clean_name == area_clean:
                fields = list(area.inline_fields)
                if not fields and self.workspace:
                    ext_area = self.workspace.get_data_area(area.name, area.scope)
                    if ext_area:
                        fields = ext_area.inline_fields
                for f in fields:
                    if f.format:
                        clean_col = f.name.lower().replace("#", "")
                        sym_id = f"sym.{area.scope.value.lower()}.{clean_col}"
                        add_field(f.name, sym_id)
                if results:
                    return results

        if self.workspace:
            data_area = self.workspace.get_data_area(raw_name, scope=None)
            if not data_area and (raw_name.startswith("#") or clean_name != raw_name):
                data_area = self.workspace.get_data_area(clean_name, scope=None)
            if data_area:
                scope_str = data_area.scope.value.lower() if data_area.scope else "local"
                for f in data_area.inline_fields:
                    if f.format:
                        clean_col = f.name.lower().replace("#", "")
                        sym_id = f"sym.{scope_str}.{clean_col}"
                        add_field(f.name, sym_id)
                if results:
                    return results

        return results

    def resolve_target_loop(self, label: Optional[str]) -> str:
        if not self.loop_stack:
            return "unknown_loop"
        if not label:
            return self.loop_stack[-1].loop_id
        target = label.upper().rstrip(".")
        for ctx in reversed(self.loop_stack):
            if ctx.label == target:
                return ctx.loop_id
        return self.loop_stack[-1].loop_id
