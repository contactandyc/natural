# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from natural.codegen.common import CodeWriter, clean_name
from natural.ir.schema import SchemaCatalog, SchemaDataType, SchemaDocument, SchemaNode, SchemaNodeType


class PrismaSchemaEmitter:
    """Emits schema.prisma model declarations from SchemaCatalog."""

    def __init__(self, catalog: SchemaCatalog, provider: str = "postgresql"):
        self.catalog = catalog
        self.provider = provider

    def _map_prisma_type(self, node: SchemaNode) -> str:
        if node.node_type in (SchemaNodeType.ARRAY_PRIMITIVE, SchemaNodeType.ARRAY_OBJECT):
            return "Json"
        dt = node.data_type
        if dt == SchemaDataType.STRING:
            return "String"
        elif dt in (SchemaDataType.INTEGER, SchemaDataType.BINARY):
            return "Int"
        elif dt == SchemaDataType.DECIMAL:
            return "Decimal"
        elif dt == SchemaDataType.BOOLEAN:
            return "Boolean"
        elif dt == SchemaDataType.DATE:
            return "DateTime"
        return "String"

    def generate(self) -> str:
        writer = CodeWriter(indent_str="  ")
        writer.emit_line("datasource db {")
        with writer.indent():
            writer.emit_line(f'provider = "{self.provider}"')
            writer.emit_line('url      = env("DATABASE_URL")')
        writer.emit_line("}")
        writer.emit_line("")
        writer.emit_line("generator client {")
        with writer.indent():
            writer.emit_line('provider = "prisma-client-js"')
        writer.emit_line("}")
        writer.emit_line("")

        for doc in sorted(self.catalog.documents.values(), key=lambda d: d.name):
            writer.emit_line(f"model {doc.class_name} {{")
            with writer.indent():
                writer.emit_line("id Int @id @default(autoincrement())")
                for node in doc.nodes:
                    if node.node_type == SchemaNodeType.GROUP:
                        continue
                    col_name = clean_name(node.name)
                    p_type = self._map_prisma_type(node)
                    writer.emit_line(f"{col_name} {p_type}?")

                # Indexes
                for idx in doc.indexes:
                    cols = ", ".join(clean_name(p.field_name) for p in idx.parts)
                    if idx.is_unique:
                        writer.emit_line(f"@@unique([{cols}])")
                    else:
                        writer.emit_line(f"@@index([{cols}])")

                writer.emit_line(f'@@map("{doc.table_or_collection_name}")')
            writer.emit_line("}")
            writer.emit_line("")

        return writer.get_code().strip()
