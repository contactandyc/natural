# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from pydantic import BaseModel, Field, SerializeAsAny
from typing import List, Optional, Dict, Any


class Provenance(BaseModel):
    line: Optional[int] = None
    source_text: Optional[str] = None


class SemanticType(BaseModel):
    base: str  # string, decimal, date, boolean, integer, unknown
    precision: Optional[int] = None
    scale: Optional[int] = None
    length: Optional[int] = None
    storage: Optional[str] = None


class Symbol(BaseModel):
    id: str
    name: str
    scope: str
    semantic_type: SemanticType
    redefine_parent: Optional[str] = None
    redefine_offset: int = 0


class SemanticNode(BaseModel):
    provenance: Optional[Provenance] = None


class SemanticSubstring(SemanticNode):
    start: "SemanticExpression"
    length: Optional["SemanticExpression"] = None


class SemanticExpression(SemanticNode):
    op: str
    symbol_id: Optional[str] = None
    value: Optional[Any] = None
    lhs: Optional["SemanticExpression"] = None
    rhs: Optional["SemanticExpression"] = None
    items: List["SemanticExpression"] = Field(default_factory=list)
    substring: Optional[SemanticSubstring] = None


SemanticSubstring.model_rebuild()
SemanticExpression.model_rebuild()


class SemanticStatement(SemanticNode):
    op: str


class AssignOp(SemanticStatement):
    op: str = "assign"
    target_id: str
    target_substring: Optional[SemanticSubstring] = None
    expr: SemanticExpression
    edit_mask: Optional[str] = None
    rounded: bool = False


class BranchOp(SemanticStatement):
    op: str = "branch"
    condition: SemanticExpression
    then_branch: List[SerializeAsAny[SemanticStatement]] = Field(default_factory=list)
    else_branch: List[SerializeAsAny[SemanticStatement]] = Field(default_factory=list)


class LoopOp(SemanticStatement):
    op: str = "loop"
    id: str
    label: Optional[str] = None
    loop_type: str = "while"  # while, until, infinite
    condition: Optional[SemanticExpression] = None
    body: List[SerializeAsAny[SemanticStatement]] = Field(default_factory=list)


class ForLoopOp(SemanticStatement):
    op: str = "for_loop"
    id: str
    label: Optional[str] = None
    variable_id: str
    start: SemanticExpression
    end: SemanticExpression
    step: SemanticExpression
    body: List[SerializeAsAny[SemanticStatement]] = Field(default_factory=list)


class BreakOp(SemanticStatement):
    op: str = "break"
    target_loop_id: str


class ContinueOp(SemanticStatement):
    op: str = "continue"
    target_loop_id: str


class ReturnOp(SemanticStatement):
    op: str = "return"


class CallSubroutineOp(SemanticStatement):
    op: str = "call_subroutine"
    subroutine_name: str


class CompressOp(SemanticStatement):
    op: str = "compress"
    target_id: str
    operands: List[SemanticExpression] = Field(default_factory=list)
    delimiter: Optional[SemanticExpression] = None
    with_delimiters: bool = False


class SeparateOp(SemanticStatement):
    op: str = "separate"
    source: SemanticExpression
    target_ids: List[str] = Field(default_factory=list)
    delimiter: Optional[SemanticExpression] = None
    ignore_remainder: bool = False


class ExamineOp(SemanticStatement):
    op: str = "examine"
    target_id: str
    pattern: Optional[SemanticExpression] = None
    replace_with: Optional[SemanticExpression] = None
    giving_number_id: Optional[str] = None
    translate_case: Optional[str] = None  # "UPPER" or "LOWER"


class MoveAllOp(SemanticStatement):
    op: str = "move_all"
    target_id: str
    fill_char: SemanticExpression


class ResetOp(SemanticStatement):
    op: str = "reset"
    target_id: str
    initial: bool = False


class EntityUpdateOp(SemanticStatement):
    op: str = "entity_update"
    target_loop_id: str
    entity: str


class EntityStoreOp(SemanticStatement):
    op: str = "entity_store"
    entity: str
    natural_view: str


class EntityDeleteOp(SemanticStatement):
    op: str = "entity_delete"
    target_loop_id: str
    entity: str


class QueryIterationOp(SemanticStatement):
    op: str = "query_iteration"
    id: str
    label: Optional[str] = None
    entity: str
    natural_view: str
    predicate: SemanticExpression
    limit: Optional[int] = None
    cardinality: str = "many"
    on_empty: List[SerializeAsAny[SemanticStatement]] = Field(default_factory=list)
    body: List[SerializeAsAny[SemanticStatement]] = Field(default_factory=list)


class ReadWorkFileOp(SemanticStatement):
    op: str = "read_work_file"
    id: str
    label: Optional[str] = None
    file_number: int
    target_ids: List[str] = Field(default_factory=list)
    body: List[SerializeAsAny[SemanticStatement]] = Field(default_factory=list)


class WriteWorkFileOp(SemanticStatement):
    op: str = "write_work_file"
    file_number: int
    operands: List[SemanticExpression] = Field(default_factory=list)


class CloseWorkFileOp(SemanticStatement):
    op: str = "close_work_file"
    file_number: int


class SubroutineBlockOp(BaseModel):
    name: str
    operations: List[SerializeAsAny[SemanticStatement]] = Field(default_factory=list)

class OnErrorOp(SemanticStatement):
    op: str = "on_error"
    body: List[SerializeAsAny[SemanticStatement]] = Field(default_factory=list)

class SemanticModule(BaseModel):
    ir_version: str = "1.0"
    module_id: str
    symbols: Dict[str, Symbol] = Field(default_factory=dict)
    operations: List[SerializeAsAny[SemanticStatement]] = Field(default_factory=list)
    subroutines: Dict[str, SubroutineBlockOp] = Field(default_factory=dict)
