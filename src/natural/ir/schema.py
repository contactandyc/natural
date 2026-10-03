# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from enum import Enum
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class SchemaNodeType(str, Enum):
    SCALAR = "scalar"
    ARRAY_PRIMITIVE = "array_primitive"  # Adabas MU (Multiple-value field)
    ARRAY_OBJECT = "array_object"        # Adabas PE (Periodic group)
    GROUP = "group"                      # Adabas GR (Non-arrayed structural group)


class SchemaDataType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    TIME = "time"
    BINARY = "binary"
    OBJECT = "object"
    UNKNOWN = "unknown"


class SchemaNode(BaseModel):
    name: str
    source_name: str
    short_name: Optional[str] = None
    level: int = 1
    node_type: SchemaNodeType = SchemaNodeType.SCALAR
    data_type: SchemaDataType = SchemaDataType.UNKNOWN
    length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    dim_start: Optional[int] = None
    dim_end: Optional[int] = None
    is_descriptor: Optional[bool] = None
    is_subdescriptor: Optional[bool] = None
    is_superdescriptor: Optional[bool] = None
    sub_fields: List[Tuple[str, int, int]] = Field(default_factory=list)
    children: List["SchemaNode"] = Field(default_factory=list)

    @property
    def is_keyed_array(self) -> bool:
        """True if the node represents an array with explicit Natural bounds."""
        return self.dim_start is not None and self.dim_end is not None

    @property
    def dimension_count(self) -> int:
        """Number of elements spanned by the Natural bounds."""
        if self.dim_start is not None and self.dim_end is not None:
            return max(0, self.dim_end - self.dim_start + 1)
        return 0

    @property
    def index_keys(self) -> List[str]:
        """Returns stringified Natural indices (e.g. ['1', '2', '3'] or ['1990', '1991', '1992'])."""
        if self.dim_start is not None and self.dim_end is not None:
            return [str(i) for i in range(self.dim_start, self.dim_end + 1)]
        return []


SchemaNode.model_rebuild()


class SchemaDocument(BaseModel):
    name: str
    class_name: str
    table_or_collection_name: str
    nodes: List[SchemaNode] = Field(default_factory=list)

    def get_node(self, name: str) -> Optional[SchemaNode]:
        clean = name.upper()
        for node in self.nodes:
            if node.name.upper() == clean or node.source_name.upper() == clean:
                return node
            for child in node.children:
                if child.name.upper() == clean or child.source_name.upper() == clean:
                    return child
        return None

    def all_scalars(self) -> List[SchemaNode]:
        return [n for n in self.nodes if n.node_type == SchemaNodeType.SCALAR]

    def all_arrays(self) -> List[SchemaNode]:
        return [n for n in self.nodes if n.node_type in (SchemaNodeType.ARRAY_PRIMITIVE, SchemaNodeType.ARRAY_OBJECT)]


class SchemaCatalog(BaseModel):
    documents: Dict[str, SchemaDocument] = Field(default_factory=dict)

    def add_document(self, doc: SchemaDocument) -> None:
        self.documents[doc.name.upper()] = doc

    def get_document(self, name: str) -> Optional[SchemaDocument]:
        return self.documents.get(name.upper())
