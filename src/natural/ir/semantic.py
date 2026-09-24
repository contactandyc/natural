# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
#
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from pydantic import BaseModel, Field, SerializeAsAny
from typing import List, Optional, Dict, Any

class Provenance(BaseModel):
    line: Optional[int] = None
    source_text: Optional[str] = None

class SemanticType(BaseModel):
    base: str
    precision: Optional[int] = None
    scale: Optional[int] = None
    length: Optional[int] = None
    storage: Optional[str] = None

class Symbol(BaseModel):
    id: str
    name: str
    scope: str
    semantic_type: SemanticType

class SemanticNode(BaseModel):
    provenance: Optional[Provenance] = None

class SemanticExpression(SemanticNode):
    op: str
    symbol_id: Optional[str] = None
    value: Optional[Any] = None
    lhs: Optional["SemanticExpression"] = None
    rhs: Optional["SemanticExpression"] = None

class SemanticStatement(SemanticNode):
    op: str

class AssignOp(SemanticStatement):
    op: str = "assign"
    target_id: str
    expr: SemanticExpression

class BranchOp(SemanticStatement):
    op: str = "branch"
    condition: SemanticExpression
    then_branch: List[SerializeAsAny[SemanticStatement]] = Field(default_factory=list)
    else_branch: List[SerializeAsAny[SemanticStatement]] = Field(default_factory=list)

class BreakOp(SemanticStatement):
    op: str = "break"
    target_loop_id: str

class ContinueOp(SemanticStatement):
    op: str = "continue"
    target_loop_id: str

class ReturnOp(SemanticStatement):
    op: str = "return"

class QueryIterationOp(SemanticStatement):
    op: str = "query_iteration"
    id: str
    entity: str
    natural_view: str
    predicate: SemanticExpression
    cardinality: str = "many"
    on_empty: List[SerializeAsAny[SemanticStatement]] = Field(default_factory=list)
    body: List[SerializeAsAny[SemanticStatement]] = Field(default_factory=list)

class SemanticModule(BaseModel):
    ir_version: str = "1.0"
    module_id: str
    symbols: Dict[str, Symbol] = Field(default_factory=dict)
    # SerializeAsAny prevents Pydantic from downcasting subclasses
    operations: List[SerializeAsAny[SemanticStatement]] = Field(default_factory=list)
