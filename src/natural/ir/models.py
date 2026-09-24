# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
#
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
    format: FieldFormat
    direction: Optional[str] = None  # IN, OUT, IN_OUT


class DataAreaRef(BaseModel):
    name: str
    scope: ScopeType
    inline_fields: List[DataField] = Field(default_factory=list)


class Expression(BaseModel):
    kind: str  # literal, ref, binary_op
    value: Optional[Any] = None
    operator: Optional[str] = None
    left: Optional["Expression"] = None
    right: Optional["Expression"] = None


Expression.model_rebuild()


class Statement(BaseModel):
    statement_type: str


class AssignStatement(Statement):
    statement_type: str = "ASSIGN"
    target: str
    value: Expression


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
    operand: Expression
    branches: List[DecideBranch] = Field(default_factory=list)
    none_branch: List[SerializeAsAny[Statement]] = Field(default_factory=list)


class FindStatement(Statement):
    statement_type: str = "FIND"
    view_name: str
    descriptor: str
    operand: Expression
    body: List[SerializeAsAny[Statement]] = Field(default_factory=list)
    on_empty: List[SerializeAsAny[Statement]] = Field(default_factory=list)


class ReadStatement(Statement):
    statement_type: str = "READ"
    view_name: str
    by_descriptor: Optional[str] = None
    body: List[SerializeAsAny[Statement]] = Field(default_factory=list)


class CallnatStatement(Statement):
    statement_type: str = "CALLNAT"
    subprogram_name: str
    parameters: List[Expression] = Field(default_factory=list)


class NaturalModule(BaseModel):
    name: str
    includes: List[str] = Field(default_factory=list)
    data_areas: List[DataAreaRef] = Field(default_factory=list)
    subroutines: Dict[str, List[SerializeAsAny[Statement]]] = Field(default_factory=dict)
    body: List[SerializeAsAny[Statement]] = Field(default_factory=list)
