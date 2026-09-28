# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, SerializeAsAny


class ScopeType(str, Enum):
    GLOBAL = "GLOBAL"
    LOCAL = "LOCAL"
    PARAMETER = "PARAMETER"


class FieldFormat(BaseModel):
    kind: str  # alphanumeric, packed_decimal, numeric, integer, date, boolean
    raw_spec: str
    length: Optional[int] = None
    digits: Optional[int] = None
    decimals: Optional[int] = None


class DataField(BaseModel):
    level: int = 1
    name: str
    format: Optional[FieldFormat] = None
    direction: Optional[str] = None
    parent_name: Optional[str] = None
    array_dim: Optional[str] = None
    init_val: Optional[Any] = None


class RedefineDefinition(BaseModel):
    level: int = 1
    target_name: str
    fields: List[DataField] = Field(default_factory=list)


class ViewField(BaseModel):
    level: int = 2
    name: str
    format: Optional[FieldFormat] = None
    array_dim: Optional[str] = None
    init_val: Optional[Any] = None


class ViewDefinition(BaseModel):
    level: int = 1
    view_name: str
    ddm_name: str
    fields: List[ViewField] = Field(default_factory=list)


class DataAreaRef(BaseModel):
    name: str
    scope: ScopeType
    inline_fields: List[DataField] = Field(default_factory=list)
    views: List[ViewDefinition] = Field(default_factory=list)
    redefines: List[RedefineDefinition] = Field(default_factory=list)


class SubstringSpec(BaseModel):
    start: "Expression"
    length: Optional["Expression"] = None


class Expression(BaseModel):
    kind: str  # literal, ref, binary_op, sys_var
    value: Optional[Any] = None
    operator: Optional[str] = None
    left: Optional["Expression"] = None
    right: Optional["Expression"] = None
    array_dim: Optional[str] = None
    array_indices: List["Expression"] = Field(default_factory=list)
    substring: Optional[SubstringSpec] = None


SubstringSpec.model_rebuild()
Expression.model_rebuild()


class Statement(BaseModel):
    statement_type: str


class AssignStatement(Statement):
    statement_type: str = "ASSIGN"
    target: Expression
    value: Expression
    rounded: bool = False


class EscapeStatement(Statement):
    statement_type: str = "ESCAPE"
    target: str  # ROUTINE, TOP, BOTTOM
    loop_label: Optional[str] = None


class ConditionalStatement(Statement):
    statement_type: str = "IF"
    condition: Expression
    then_branch: List[SerializeAsAny[Statement]] = Field(default_factory=list)
    else_branch: List[SerializeAsAny[Statement]] = Field(default_factory=list)


class DecideBranch(BaseModel):
    value: Expression
    statements: List[SerializeAsAny[Statement]] = Field(default_factory=list)


class DecideStatement(Statement):
    statement_type: str = "DECIDE"
    decide_type: str = "ON"  # ON or FOR
    operand: Optional[Expression] = None
    branches: List[DecideBranch] = Field(default_factory=list)
    none_branch: List[SerializeAsAny[Statement]] = Field(default_factory=list)


class FindStatement(Statement):
    statement_type: str = "FIND"
    label: Optional[str] = None
    view_name: str
    descriptor: Optional[str] = None
    operand: Optional[Expression] = None
    criteria: Optional[Expression] = None
    limit: Optional[int] = None
    body: List[SerializeAsAny[Statement]] = Field(default_factory=list)
    on_empty: List[SerializeAsAny[Statement]] = Field(default_factory=list)


class ReadStatement(Statement):
    statement_type: str = "READ"
    label: Optional[str] = None
    view_name: str
    descriptor: Optional[str] = None
    by_descriptor: Optional[str] = None
    starting_from: Optional[Expression] = None
    thru_value: Optional[Expression] = None
    limit: Optional[int] = None
    body: List[SerializeAsAny[Statement]] = Field(default_factory=list)


class CallnatStatement(Statement):
    statement_type: str = "CALLNAT"
    subprogram_name: str
    parameters: List[Expression] = Field(default_factory=list)


class PerformStatement(Statement):
    statement_type: str = "PERFORM"
    subroutine_name: str


class LoopStatement(Statement):
    statement_type: str = "REPEAT"
    label: Optional[str] = None
    loop_type: str = "INFINITE"  # WHILE, UNTIL, UNTIL_POST, INFINITE
    condition: Optional[Expression] = None
    body: List[SerializeAsAny[Statement]] = Field(default_factory=list)


class ForStatement(Statement):
    statement_type: str = "FOR"
    label: Optional[str] = None
    variable: str
    start_expr: Expression
    end_expr: Expression
    step_expr: Optional[Expression] = None
    body: List[SerializeAsAny[Statement]] = Field(default_factory=list)


class MoveStatement(Statement):
    statement_type: str = "MOVE"
    source: Expression
    target: Expression
    edit_mask: Optional[str] = None
    is_move_all: bool = False


class CompressStatement(Statement):
    statement_type: str = "COMPRESS"
    operands: List[Expression] = Field(default_factory=list)
    target: Expression
    delimiter: Optional[Expression] = None
    with_delimiters: bool = False


class SeparateStatement(Statement):
    statement_type: str = "SEPARATE"
    source: Expression
    targets: List[Expression] = Field(default_factory=list)
    delimiter: Optional[Expression] = None
    ignore_remainder: bool = False


class ExamineStatement(Statement):
    statement_type: str = "EXAMINE"
    target: Expression
    pattern: Optional[Expression] = None
    replace_with: Optional[Expression] = None
    giving_number: Optional[Expression] = None
    translate_case: Optional[str] = None  # "UPPER" or "LOWER"


class ResetStatement(Statement):
    statement_type: str = "RESET"
    targets: List[Expression] = Field(default_factory=list)
    initial: bool = False


class InputModifier(BaseModel):
    key: str
    value: Expression


class InputStatement(Statement):
    statement_type: str = "INPUT"
    modifiers: List[InputModifier] = Field(default_factory=list)
    fields: List[Any] = Field(default_factory=list)


class PrintStatement(Statement):
    statement_type: str = "PRINT"
    fields: List[Any] = Field(default_factory=list)


class WriteStatement(Statement):
    statement_type: str = "WRITE"
    items: List[Any] = Field(default_factory=list)


class UpdateStatement(Statement):
    statement_type: str = "UPDATE"
    loop_label: Optional[str] = None


class DeleteStatement(Statement):
    statement_type: str = "DELETE"
    loop_label: Optional[str] = None


class StoreStatement(Statement):
    statement_type: str = "STORE"
    view_name: str


class GetStatement(Statement):
    statement_type: str = "GET"
    view_name: str
    arguments: List[Expression] = Field(default_factory=list)


class GetSameStatement(Statement):
    statement_type: str = "GET_SAME"
    view_name: Optional[str] = None


class EndTransactionStatement(Statement):
    statement_type: str = "END_TRANSACTION"
    operand: Optional[Expression] = None


class BackoutTransactionStatement(Statement):
    statement_type: str = "BACKOUT_TRANSACTION"


class StopStatement(Statement):
    statement_type: str = "STOP"


class TerminateStatement(Statement):
    statement_type: str = "TERMINATE"


class AtStartOfDataStatement(Statement):
    statement_type: str = "AT_START_OF_DATA"
    body: List[SerializeAsAny[Statement]] = Field(default_factory=list)


class AtEndOfDataStatement(Statement):
    statement_type: str = "AT_END_OF_DATA"
    body: List[SerializeAsAny[Statement]] = Field(default_factory=list)


class ResizeArrayStatement(Statement):
    statement_type: str = "RESIZE_ARRAY"
    action: str = "RESIZE"
    array_name: str
    dimensions: List[Expression] = Field(default_factory=list)


class ReadWorkFileStatement(Statement):
    statement_type: str = "READ_WORK_FILE"
    label: Optional[str] = None
    file_number: int
    fields: List[Expression] = Field(default_factory=list)
    body: List[SerializeAsAny[Statement]] = Field(default_factory=list)


class WriteWorkFileStatement(Statement):
    statement_type: str = "WRITE_WORK_FILE"
    file_number: int
    fields: List[Expression] = Field(default_factory=list)


class CloseWorkFileStatement(Statement):
    statement_type: str = "CLOSE_WORK_FILE"
    file_number: int


class OnErrorBlockStatement(Statement):
    statement_type: str = "ON_ERROR"
    body: List[SerializeAsAny[Statement]] = Field(default_factory=list)


class SubroutineDefinition(BaseModel):
    name: str
    body: List[SerializeAsAny[Statement]] = Field(default_factory=list)


class NaturalModule(BaseModel):
    name: str
    includes: List[str] = Field(default_factory=list)
    data_areas: List[DataAreaRef] = Field(default_factory=list)
    subroutines: Dict[str, List[SerializeAsAny[Statement]]] = Field(default_factory=dict)
    body: List[SerializeAsAny[Statement]] = Field(default_factory=list)
