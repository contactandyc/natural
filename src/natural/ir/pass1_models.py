# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from pydantic import BaseModel, Field
from typing import List, Any, Optional


class Pass1Node(BaseModel):
    pass


class RawStatement(Pass1Node):
    text: str


class DefineDataBlock(Pass1Node):
    raw_content: str


class BlockNode(Pass1Node):
    label: Optional[str] = None
    raw_clause: str
    body: List[Any] = Field(default_factory=list)


class FindBlock(BlockNode):
    pass


class ReadBlock(BlockNode):
    pass


class HistogramBlock(BlockNode):
    pass


class RepeatBlock(BlockNode):
    is_post_test: bool = False


class ForBlock(BlockNode):
    pass


class ReadWorkBlock(BlockNode):
    pass


class IfBlock(BlockNode):
    else_body: List[Any] = Field(default_factory=list)


class DecideBranchBlock(BlockNode):
    pass


class NoneBranchBlock(BlockNode):
    pass


class DecideBlock(BlockNode):
    decide_type: str = "ON"  # "ON" or "FOR"
    branches: List[DecideBranchBlock] = Field(default_factory=list)
    none_branch: Optional[NoneBranchBlock] = None


class SubroutineBlock(Pass1Node):
    name: str
    body: List[Any] = Field(default_factory=list)


class FunctionBlock(Pass1Node):
    name: str
    returns_clause: Optional[str] = None
    body: List[Any] = Field(default_factory=list)


class OnErrorBlock(Pass1Node):
    body: List[Any] = Field(default_factory=list)


class AtStartBlock(Pass1Node):
    body: List[Any] = Field(default_factory=list)


class AtEndBlock(Pass1Node):
    body: List[Any] = Field(default_factory=list)


class AtBreakBlock(BlockNode):
    pass


class BeforeBreakBlock(Pass1Node):
    body: List[Any] = Field(default_factory=list)


class Pass1Module(BaseModel):
    module_name: str
    statements: List[Any] = Field(default_factory=list)
