# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import List, Optional, Union
from natural.codegen.common import CodeWriter, clean_name
from natural.ir.models import DataAreaRef
from natural.ir.schema import (
    SchemaCatalog,
    SchemaDataType,
    SchemaNode,
    SchemaNodeType,
)
from natural.normalizer.schema_builder import SchemaBuilder

FALLBACK_ORM_SOURCE = """from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

def __getattr__(name):
    if name.startswith("__") and name.endswith("__"):
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    cls_dict = {
        '__tablename__': name.lower(),
        'id': Column('id', Integer, primary_key=True, autoincrement=True),
        'name': Column('name', String(255), default=""),
    }
    return type(name, (Base,), cls_dict)
"""


class ORMEmitter:
    def __init__(
            self,
            schema_source: Union[SchemaCatalog, List[DataAreaRef]],
            writer: Optional[CodeWriter] = None,
    ):
        if isinstance(schema_source, SchemaCatalog):
            self.catalog = schema_source
        else:
            self.catalog = SchemaBuilder(schema_source).build_catalog()
        self.writer = writer or CodeWriter()

    @property
    def lines(self) -> List[str]:
        return self.writer.lines

    def _clean_name(self, name: str) -> str:
        return clean_name(name)

    def emit_line(self, line: str = "", indent_level: int = 0) -> None:
        self.writer.emit_line(line, indent_offset=indent_level)

    def _map_sa_type(self, node: SchemaNode) -> str:
        if node.data_type == SchemaDataType.STRING:
            length = node.length if node.length else 255
            return f"String({length})"
        elif node.data_type == SchemaDataType.DECIMAL:
            prec = node.precision if node.precision is not None else 10
            scale = node.scale if node.scale is not None else 0
            return f"Numeric({prec}, {scale})"
        elif node.data_type == SchemaDataType.INTEGER:
            return "Integer"
        elif node.data_type == SchemaDataType.BOOLEAN:
            return "Boolean"
        elif node.data_type == SchemaDataType.DATE:
            return "Date"
        elif node.data_type == SchemaDataType.BINARY:
            return "Integer"
        return "String(255)"

    def _build_array_default(self, node: SchemaNode) -> str:
        if not node.index_keys:
            return "dict"

        if node.node_type == SchemaNodeType.ARRAY_OBJECT:
            child_defaults = []
            for child in node.children:
                ch_name = clean_name(child.name)
                if child.node_type == SchemaNodeType.ARRAY_PRIMITIVE:
                    inner_def = self._build_array_default(child)
                    ch_val = inner_def[len("lambda: "):] if inner_def.startswith("lambda: ") else "{}"
                elif child.data_type == SchemaDataType.STRING:
                    ch_val = "''"
                elif child.data_type == SchemaDataType.DECIMAL:
                    ch_val = "Decimal('0')"
                elif child.data_type in (SchemaDataType.INTEGER, SchemaDataType.BINARY):
                    ch_val = "0"
                elif child.data_type == SchemaDataType.BOOLEAN:
                    ch_val = "False"
                else:
                    ch_val = "None"
                child_defaults.append(f"'{ch_name}': {ch_val}")
            inner_obj = "{" + ", ".join(child_defaults) + "}"
            items = ", ".join(f"'{k}': {inner_obj}" for k in node.index_keys)
            return f"lambda: {{{items}}}"

        # ARRAY_PRIMITIVE
        if node.data_type == SchemaDataType.STRING:
            items = ", ".join(f"'{k}': ''" for k in node.index_keys)
        elif node.data_type == SchemaDataType.DECIMAL:
            items = ", ".join(f"'{k}': Decimal('0')" for k in node.index_keys)
        elif node.data_type in (SchemaDataType.INTEGER, SchemaDataType.BINARY):
            items = ", ".join(f"'{k}': 0" for k in node.index_keys)
        elif node.data_type == SchemaDataType.BOOLEAN:
            items = ", ".join(f"'{k}': False" for k in node.index_keys)
        else:
            items = ", ".join(f"'{k}': None" for k in node.index_keys)

        return f"lambda: {{{items}}}"

    def generate(self) -> str:
        has_indexes = any(doc.indexes for doc in self.catalog.documents.values())
        has_relations = any(doc.relations for doc in self.catalog.documents.values())
        has_fks = any(
            any(n.is_foreign_key for n in doc.nodes)
            for doc in self.catalog.documents.values()
        )

        extra_sa = []
        if has_indexes:
            extra_sa.append("Index")
        if has_fks:
            extra_sa.append("ForeignKey")

        sa_imports = f", {', '.join(extra_sa)}" if extra_sa else ""

        self.emit_line("from decimal import Decimal")
        if has_relations:
            self.emit_line("from natural_runtime import AdabasArrayProxy, AdabasObjectArrayProxy")
        self.emit_line(f"from sqlalchemy import Column, String, Numeric, Integer, Boolean, JSON, Date{sa_imports}")
        if has_relations:
            self.emit_line("from sqlalchemy.orm import declarative_base, relationship")
        else:
            self.emit_line("from sqlalchemy.orm import declarative_base")
        self.emit_line("")
        self.emit_line("Base = declarative_base()")
        self.emit_line("")

        for doc in self.catalog.documents.values():
            class_name = doc.class_name
            table_name = doc.table_or_collection_name

            self.emit_line(f"class {class_name}(Base):")
            with self.writer.indent():
                self.emit_line(f"__tablename__ = '{table_name}'")
                self.emit_line("")

                has_explicit_pk = any(n.is_primary_key for n in doc.nodes)
                if has_relations and not has_explicit_pk:
                    self.emit_line("id = Column('id', Integer, primary_key=True, autoincrement=True)")

                for i, node in enumerate(doc.nodes):
                    if node.node_type == SchemaNodeType.GROUP:
                        continue

                    col_name = clean_name(node.name)
                    pk_arg = ", primary_key=True" if node.is_primary_key or (not has_relations and not has_explicit_pk and i == 0) else ""
                    fk_arg = f", ForeignKey('{node.references_table}.id')" if node.is_foreign_key and node.references_table else ""

                    if node.node_type in (SchemaNodeType.ARRAY_PRIMITIVE, SchemaNodeType.ARRAY_OBJECT):
                        default_expr = self._build_array_default(node)
                        self.emit_line(
                            f"{col_name} = Column('{node.source_name.lower()}', JSON, default={default_expr}{pk_arg})"
                        )
                    else:
                        sa_type = self._map_sa_type(node)
                        self.emit_line(f"{col_name} = Column('{node.source_name.lower()}', {sa_type}{fk_arg}{pk_arg})")

                # Emitted Relationships
                for rel in doc.relations:
                    self.emit_line(
                        f"{rel.name} = relationship('{rel.child_class_name}', cascade='all, delete-orphan', lazy='joined')"
                    )

                # Emitted Indexes
                if doc.indexes:
                    self.emit_line("")
                    idx_items = []
                    for idx in doc.indexes:
                        cols = ", ".join(repr(p.field_name) for p in idx.parts)
                        uniq = ", unique=True" if idx.is_unique else ""
                        idx_items.append(f"Index({idx.name!r}, {cols}{uniq})")
                    self.emit_line(f"__table_args__ = ({', '.join(idx_items)},)")

                # Proxy descriptors for 1NF relationships
                for rel in doc.relations:
                    self.emit_line("")
                    self.emit_line("@property")
                    self.emit_line(f"def {rel.proxy_property}(self):")
                    with self.writer.indent():
                        if not rel.is_object_array:
                            self.emit_line(
                                f"return AdabasArrayProxy(self.{rel.name}, {rel.child_class_name}, value_attr='{rel.value_field}')"
                            )
                        else:
                            self.emit_line(
                                f"return AdabasObjectArrayProxy(self.{rel.name}, {rel.child_class_name})"
                            )

            self.emit_line("")

        return self.writer.get_code()
