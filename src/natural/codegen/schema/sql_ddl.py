# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import Dict
from natural.codegen.common import CodeWriter, clean_name
from natural.ir.schema import SchemaCatalog, SchemaDataType, SchemaDocument, SchemaNode, SchemaNodeType


class SqlDdlEmitter:
    """Emits production-ready SQL DDL (PostgreSQL, MySQL, SQLite, Oracle)."""

    def __init__(self, catalog: SchemaCatalog, dialect: str = "postgres"):
        self.catalog = catalog
        self.dialect = dialect.lower()

    def _map_sql_type(self, node: SchemaNode) -> str:
        if node.node_type in (SchemaNodeType.ARRAY_PRIMITIVE, SchemaNodeType.ARRAY_OBJECT):
            if self.dialect in ("postgres", "postgresql"):
                return "JSONB"
            return "JSON"

        dt = node.data_type
        if dt == SchemaDataType.STRING:
            length = node.length or 255
            return f"VARCHAR({length})"
        elif dt == SchemaDataType.DECIMAL:
            prec = node.precision or 10
            scale = node.scale or 0
            return f"NUMERIC({prec}, {scale})"
        elif dt in (SchemaDataType.INTEGER, SchemaDataType.BINARY):
            return "INTEGER"
        elif dt == SchemaDataType.BOOLEAN:
            return "BOOLEAN" if self.dialect != "oracle" else "NUMBER(1)"
        elif dt == SchemaDataType.DATE:
            return "DATE"
        return "VARCHAR(255)"

    def emit_document(self, doc: SchemaDocument) -> str:
        writer = CodeWriter(indent_str="    ")
        table_name = doc.table_or_collection_name
        has_explicit_pk = any(n.is_primary_key for n in doc.nodes)

        writer.emit_line(f"CREATE TABLE {table_name} (")
        with writer.indent():
            if not has_explicit_pk:
                if self.dialect in ("postgres", "postgresql"):
                    pk_line = "id SERIAL PRIMARY KEY,"
                elif self.dialect == "sqlite":
                    pk_line = "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                elif self.dialect == "mysql":
                    pk_line = "id INT AUTO_INCREMENT PRIMARY KEY,"
                else:
                    pk_line = "id INT PRIMARY KEY,"
                writer.emit_line(pk_line)

            for i, node in enumerate(doc.nodes):
                if node.node_type == SchemaNodeType.GROUP:
                    continue
                col_name = clean_name(node.name)
                sql_type = self._map_sql_type(node)

                pk_clause = " PRIMARY KEY" if node.is_primary_key else ""
                fk_clause = f" REFERENCES {node.references_table}(id) ON DELETE CASCADE" if node.is_foreign_key and node.references_table else ""

                is_last = (i == len(doc.nodes) - 1)
                comma = "" if is_last else ","
                writer.emit_line(f"{col_name} {sql_type}{fk_clause}{pk_clause}{comma}")

        writer.emit_line(");")
        writer.emit_line("")

        # Emit Indexes
        for idx in doc.indexes:
            col_list = ", ".join(clean_name(p.field_name) for p in idx.parts)
            uniq = "UNIQUE " if idx.is_unique else ""
            writer.emit_line(f"CREATE {uniq}INDEX {idx.name} ON {table_name} ({col_list});")

        return writer.get_code().strip()

    def generate(self) -> Dict[str, str]:
        outputs = {}
        for doc in self.catalog.documents.values():
            outputs[f"{doc.table_or_collection_name}.sql"] = self.emit_document(doc)
        return outputs
