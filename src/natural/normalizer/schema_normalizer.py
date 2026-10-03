# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import List, Tuple
from natural.codegen.common.naming import clean_name, to_pascal_case
from natural.ir.schema import (
    SchemaCatalog,
    SchemaDataType,
    SchemaDocument,
    SchemaIndex,
    SchemaIndexPart,
    SchemaIndexType,
    SchemaNode,
    SchemaNodeType,
    SchemaRelation,
)


class SchemaNormalizer:
    """Transforms hierarchical SchemaCatalog documents into 1st Normal Form (1NF) relational schemas."""

    def normalize(self, catalog: SchemaCatalog) -> SchemaCatalog:
        normalized = SchemaCatalog()
        parents: List[SchemaDocument] = []
        children: List[SchemaDocument] = []

        for doc in catalog.documents.values():
            parent_doc, child_docs = self._normalize_document(doc)
            parents.append(parent_doc)
            children.extend(child_docs)

        for doc in parents:
            normalized.add_document(doc)
        for doc in children:
            normalized.add_document(doc)

        return normalized

    def _normalize_document(
            self,
            doc: SchemaDocument,
    ) -> Tuple[SchemaDocument, List[SchemaDocument]]:
        retained_nodes: List[SchemaNode] = []
        child_docs: List[SchemaDocument] = []
        relations: List[SchemaRelation] = []

        parent_table = doc.table_or_collection_name
        parent_class = doc.class_name

        for node in doc.nodes:
            if node.node_type == SchemaNodeType.ARRAY_PRIMITIVE:
                child_doc = self._create_primitive_child(parent_table, parent_class, node)
                child_docs.append(child_doc)
                relations.append(
                    SchemaRelation(
                        name=f"_{clean_name(node.name)}",
                        target_document=child_doc.name,
                        foreign_key_col=f"{parent_table}_id",
                        is_collection=True,
                        proxy_property=clean_name(node.name),
                        value_field="value",
                        child_class_name=child_doc.class_name,
                        is_object_array=False,
                    )
                )
            elif node.node_type == SchemaNodeType.ARRAY_OBJECT:
                child_doc, nested_children = self._create_object_child(parent_table, parent_class, node)
                child_docs.append(child_doc)
                child_docs.extend(nested_children)
                relations.append(
                    SchemaRelation(
                        name=f"_{clean_name(node.name)}",
                        target_document=child_doc.name,
                        foreign_key_col=f"{parent_table}_id",
                        is_collection=True,
                        proxy_property=clean_name(node.name),
                        child_class_name=child_doc.class_name,
                        is_object_array=True,
                    )
                )
            else:
                retained_nodes.append(node)

        normalized_parent = SchemaDocument(
            name=doc.name,
            class_name=doc.class_name,
            table_or_collection_name=doc.table_or_collection_name,
            parent_document=doc.parent_document,
            nodes=retained_nodes,
            indexes=doc.indexes,
            relations=relations,
        )

        return normalized_parent, child_docs

    def _create_primitive_child(
            self,
            parent_table: str,
            parent_class: str,
            node: SchemaNode,
    ) -> SchemaDocument:
        child_suffix = clean_name(node.name)
        child_table = f"{parent_table}_{child_suffix}"
        child_class = f"{parent_class}{to_pascal_case(child_suffix)}"
        fk_col = f"{parent_table}_id"

        nodes = [
            SchemaNode(
                name="id",
                source_name="ID",
                level=1,
                node_type=SchemaNodeType.SCALAR,
                data_type=SchemaDataType.INTEGER,
                is_primary_key=True,
            ),
            SchemaNode(
                name=fk_col,
                source_name=fk_col.upper(),
                level=1,
                node_type=SchemaNodeType.SCALAR,
                data_type=SchemaDataType.INTEGER,
                is_foreign_key=True,
                references_table=parent_table,
            ),
            SchemaNode(
                name="natural_index",
                source_name="NATURAL_INDEX",
                level=1,
                node_type=SchemaNodeType.SCALAR,
                data_type=SchemaDataType.INTEGER,
            ),
            SchemaNode(
                name="value",
                source_name=node.source_name,
                level=1,
                node_type=SchemaNodeType.SCALAR,
                data_type=node.data_type,
                length=node.length,
                precision=node.precision,
                scale=node.scale,
            ),
        ]

        indexes = [
            SchemaIndex(
                name=f"uq_{child_table}_idx",
                source_name="NATURAL_INDEX",
                index_type=SchemaIndexType.UNIQUE,
                is_unique=True,
                parts=[
                    SchemaIndexPart(field_name=fk_col),
                    SchemaIndexPart(field_name="natural_index"),
                ],
            )
        ]

        return SchemaDocument(
            name=f"{parent_table.upper()}_{node.source_name}",
            class_name=child_class,
            table_or_collection_name=child_table,
            parent_document=parent_table,
            nodes=nodes,
            indexes=indexes,
            relations=[],
        )

    def _create_object_child(
            self,
            parent_table: str,
            parent_class: str,
            node: SchemaNode,
    ) -> Tuple[SchemaDocument, List[SchemaDocument]]:
        child_suffix = clean_name(node.name)
        child_table = f"{parent_table}_{child_suffix}"
        child_class = f"{parent_class}{to_pascal_case(child_suffix)}"
        fk_col = f"{parent_table}_id"

        nodes = [
            SchemaNode(
                name="id",
                source_name="ID",
                level=1,
                node_type=SchemaNodeType.SCALAR,
                data_type=SchemaDataType.INTEGER,
                is_primary_key=True,
            ),
            SchemaNode(
                name=fk_col,
                source_name=fk_col.upper(),
                level=1,
                node_type=SchemaNodeType.SCALAR,
                data_type=SchemaDataType.INTEGER,
                is_foreign_key=True,
                references_table=parent_table,
            ),
            SchemaNode(
                name="natural_index",
                source_name="NATURAL_INDEX",
                level=1,
                node_type=SchemaNodeType.SCALAR,
                data_type=SchemaDataType.INTEGER,
            ),
        ]

        nested_children: List[SchemaDocument] = []
        relations: List[SchemaRelation] = []

        for ch in node.children:
            if ch.node_type == SchemaNodeType.ARRAY_PRIMITIVE:
                sub_child = self._create_primitive_child(child_table, child_class, ch)
                nested_children.append(sub_child)
                relations.append(
                    SchemaRelation(
                        name=f"_{clean_name(ch.name)}",
                        target_document=sub_child.name,
                        foreign_key_col=f"{child_table}_id",
                        is_collection=True,
                        proxy_property=clean_name(ch.name),
                        value_field="value",
                        child_class_name=sub_child.class_name,
                        is_object_array=False,
                    )
                )
            else:
                nodes.append(ch)

        indexes = [
            SchemaIndex(
                name=f"uq_{child_table}_idx",
                source_name="NATURAL_INDEX",
                index_type=SchemaIndexType.UNIQUE,
                is_unique=True,
                parts=[
                    SchemaIndexPart(field_name=fk_col),
                    SchemaIndexPart(field_name="natural_index"),
                ],
            )
        ]

        doc = SchemaDocument(
            name=f"{parent_table.upper()}_{node.source_name}",
            class_name=child_class,
            table_or_collection_name=child_table,
            parent_document=parent_table,
            nodes=nodes,
            indexes=indexes,
            relations=relations,
        )

        return doc, nested_children
