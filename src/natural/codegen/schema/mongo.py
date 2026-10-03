# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import Dict
from natural.codegen.common import CodeWriter, clean_name
from natural.ir.schema import SchemaCatalog, SchemaDataType, SchemaDocument, SchemaNode, SchemaNodeType


class MongoSchemaEmitter:
    """Emits Mongoose (TypeScript/JavaScript) document models from SchemaCatalog."""

    def __init__(self, catalog: SchemaCatalog):
        self.catalog = catalog

    def _map_mongoose_type(self, node: SchemaNode) -> str:
        dt = node.data_type
        if dt == SchemaDataType.STRING:
            return "String"
        elif dt in (SchemaDataType.INTEGER, SchemaDataType.BINARY):
            return "Number"
        elif dt == SchemaDataType.DECIMAL:
            return "Schema.Types.Decimal128"
        elif dt == SchemaDataType.BOOLEAN:
            return "Boolean"
        elif dt == SchemaDataType.DATE:
            return "Date"
        return "String"

    def emit_document(self, doc: SchemaDocument) -> str:
        writer = CodeWriter(indent_str="  ")
        class_name = doc.class_name

        writer.emit_line("import { Schema, model, Document } from 'mongoose';")
        writer.emit_line("")

        # Emit nested subschemas for Periodic Groups (PE)
        for node in doc.nodes:
            if node.node_type == SchemaNodeType.ARRAY_OBJECT:
                sub_schema_name = f"{class_name}_{clean_name(node.name).title()}"
                writer.emit_line(f"const {sub_schema_name}Schema = new Schema({{")
                with writer.indent():
                    for child in node.children:
                        ch_name = clean_name(child.name)
                        if child.node_type == SchemaNodeType.ARRAY_PRIMITIVE:
                            ch_t = self._map_mongoose_type(child)
                            writer.emit_line(f"{ch_name}: {{ type: Map, of: {ch_t} }},")
                        else:
                            ch_t = self._map_mongoose_type(child)
                            writer.emit_line(f"{ch_name}: {{ type: {ch_t} }},")
                writer.emit_line("}, { _id: false });")
                writer.emit_line("")

        # Emit Root Schema
        writer.emit_line(f"const {class_name}Schema = new Schema({{")
        with writer.indent():
            for node in doc.nodes:
                if node.node_type == SchemaNodeType.GROUP:
                    continue
                col_name = clean_name(node.name)
                if node.node_type == SchemaNodeType.ARRAY_OBJECT:
                    sub_schema_name = f"{class_name}_{clean_name(node.name).title()}"
                    writer.emit_line(f"{col_name}: {{ type: Map, of: {sub_schema_name}Schema }},")
                elif node.node_type == SchemaNodeType.ARRAY_PRIMITIVE:
                    mg_type = self._map_mongoose_type(node)
                    writer.emit_line(f"{col_name}: {{ type: Map, of: {mg_type} }},")
                else:
                    mg_type = self._map_mongoose_type(node)
                    writer.emit_line(f"{col_name}: {{ type: {mg_type} }},")

        writer.emit_line("});")
        writer.emit_line("")

        # Emit Mongoose Indexes
        for idx in doc.indexes:
            idx_fields = ", ".join(f"{clean_name(p.field_name)}: 1" for p in idx.parts)
            uniq_arg = ", { unique: true }" if idx.is_unique else ""
            writer.emit_line(f"{class_name}Schema.index({{ {idx_fields} }}{uniq_arg});")

        writer.emit_line("")
        writer.emit_line(f"export const {class_name} = model('{class_name}', {class_name}Schema);")
        return writer.get_code().strip()

    def generate(self) -> Dict[str, str]:
        outputs = {}
        for doc in self.catalog.documents.values():
            outputs[f"{doc.table_or_collection_name}.ts"] = self.emit_document(doc)
        return outputs
