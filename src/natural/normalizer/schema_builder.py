# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import List, Optional
from natural.codegen.common.naming import clean_name, to_pascal_case
from natural.ir.models import DataAreaRef, DataField
from natural.ir.schema import (
    SchemaCatalog,
    SchemaDataType,
    SchemaDocument,
    SchemaNode,
    SchemaNodeType,
)


class SchemaBuilder:
    """Builds a target-agnostic hierarchical SchemaCatalog (IR-S) from AST DDMs."""

    def __init__(self, ddms: Optional[List[DataAreaRef]] = None):
        self.ddms = ddms or []

    def _map_data_type(self, kind: Optional[str]) -> SchemaDataType:
        if not kind:
            return SchemaDataType.UNKNOWN
        kind_map = {
            "alphanumeric": SchemaDataType.STRING,
            "packed_decimal": SchemaDataType.DECIMAL,
            "numeric": SchemaDataType.DECIMAL,
            "integer": SchemaDataType.INTEGER,
            "binary": SchemaDataType.BINARY,
            "boolean": SchemaDataType.BOOLEAN,
            "date": SchemaDataType.DATE,
            "periodic_group": SchemaDataType.OBJECT,
        }
        return kind_map.get(kind, SchemaDataType.UNKNOWN)

    def _convert_field(self, field: DataField) -> SchemaNode:
        kind = field.format.kind if field.format else None
        data_type = self._map_data_type(kind)

        if getattr(field, "is_periodic", False) or kind == "periodic_group":
            node_type = SchemaNodeType.ARRAY_OBJECT
        elif getattr(field, "is_multiple", False) or (field.dim_end and field.dim_end > 1):
            node_type = SchemaNodeType.ARRAY_PRIMITIVE
        elif field.level == 1 and not field.format:
            node_type = SchemaNodeType.GROUP
        else:
            node_type = SchemaNodeType.SCALAR

        if data_type == SchemaDataType.STRING:
            length = field.format.length if field.format else None
            prec = None
            scale = None
        elif data_type == SchemaDataType.DECIMAL:
            length = None
            prec = field.format.digits if field.format else None
            scale = field.format.decimals if field.format else None
        elif data_type == SchemaDataType.INTEGER:
            length = field.format.length or (field.format.digits if field.format else 4)
            prec = None
            scale = None
        else:
            length = field.format.length if field.format else None
            prec = field.format.digits if field.format else None
            scale = field.format.decimals if field.format else None

        has_explicit_bounds = (
                field.dim_end is not None
                and node_type in (SchemaNodeType.ARRAY_PRIMITIVE, SchemaNodeType.ARRAY_OBJECT)
        )

        return SchemaNode(
            name=clean_name(field.name),
            source_name=field.name,
            level=field.level,
            node_type=node_type,
            data_type=data_type,
            length=length,
            precision=prec,
            scale=scale,
            dim_start=field.dim_start if has_explicit_bounds else None,
            dim_end=field.dim_end if has_explicit_bounds else None,
            is_superdescriptor=True if bool(field.sub_fields) else None,
            sub_fields=field.sub_fields,
            children=[],
        )

    def build_document(self, ddm: DataAreaRef) -> SchemaDocument:
        cleaned_ddm = clean_name(ddm.name).replace("_view", "")
        class_name = to_pascal_case(cleaned_ddm)
        table_name = cleaned_ddm

        doc = SchemaDocument(
            name=ddm.name.upper(),
            class_name=class_name,
            table_or_collection_name=table_name,
            nodes=[],
        )

        current_parent_node: Optional[SchemaNode] = None

        for field in ddm.inline_fields:
            node = self._convert_field(field)

            if field.level == 1:
                doc.nodes.append(node)
                if node.node_type in (SchemaNodeType.ARRAY_OBJECT, SchemaNodeType.GROUP):
                    current_parent_node = node
                else:
                    current_parent_node = None
            elif field.level > 1 and current_parent_node:
                current_parent_node.children.append(node)
            else:
                doc.nodes.append(node)

        return doc

    def build_catalog(self, ddms: Optional[List[DataAreaRef]] = None) -> SchemaCatalog:
        sources = ddms if ddms is not None else self.ddms
        catalog = SchemaCatalog()
        for ddm in sorted(sources, key=lambda d: d.name):
            catalog.add_document(self.build_document(ddm))
        return catalog
