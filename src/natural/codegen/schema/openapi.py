# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import Any, Dict
import yaml
from natural.codegen.common import clean_name
from natural.ir.schema import SchemaCatalog, SchemaDataType, SchemaDocument, SchemaNode, SchemaNodeType


class OpenApiSchemaEmitter:
    """Emits OpenAPI 3.0 specification YAML containing components/schemas from SchemaCatalog."""

    def __init__(self, catalog: SchemaCatalog, title: str = "Natural Data Models", version: str = "1.0.0"):
        self.catalog = catalog
        self.title = title
        self.version = version

    def _convert_node(self, node: SchemaNode) -> Dict[str, Any]:
        if node.node_type == SchemaNodeType.ARRAY_OBJECT:
            child_props = {clean_name(ch.name): self._convert_node(ch) for ch in node.children}
            return {
                "type": "object",
                "description": f"Periodic Group: {node.source_name}",
                "additionalProperties": {
                    "type": "object",
                    "properties": child_props,
                },
            }
        elif node.node_type == SchemaNodeType.ARRAY_PRIMITIVE:
            inner_type = "string" if node.data_type == SchemaDataType.STRING else ("number" if node.data_type == SchemaDataType.DECIMAL else "integer")
            return {
                "type": "object",
                "description": f"Multiple Value Field: {node.source_name}",
                "additionalProperties": {"type": inner_type},
            }

        dt = node.data_type
        if dt == SchemaDataType.STRING:
            spec: Dict[str, Any] = {"type": "string"}
            if node.length:
                spec["maxLength"] = node.length
            return spec
        elif dt == SchemaDataType.DECIMAL:
            return {"type": "number", "format": "decimal"}
        elif dt in (SchemaDataType.INTEGER, SchemaDataType.BINARY):
            return {"type": "integer"}
        elif dt == SchemaDataType.BOOLEAN:
            return {"type": "boolean"}
        elif dt == SchemaDataType.DATE:
            return {"type": "string", "format": "date"}
        return {"type": "string"}

    def generate(self) -> str:
        schemas: Dict[str, Any] = {}
        for doc in sorted(self.catalog.documents.values(), key=lambda d: d.name):
            properties: Dict[str, Any] = {"id": {"type": "integer", "description": "Synthetic Primary Key"}}
            for node in doc.nodes:
                if node.node_type == SchemaNodeType.GROUP:
                    continue
                properties[clean_name(node.name)] = self._convert_node(node)

            schemas[doc.class_name] = {
                "type": "object",
                "description": f"Generated from Adabas DDM: {doc.name}",
                "properties": properties,
            }

        doc_dict = {
            "openapi": "3.0.3",
            "info": {"title": self.title, "version": self.version},
            "paths": {},
            "components": {"schemas": schemas},
        }
        return yaml.dump(doc_dict, sort_keys=False, indent=2)
