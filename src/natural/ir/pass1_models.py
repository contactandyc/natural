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
    raw_clause: str
    body: List[Any] = Field(default_factory=list)

class FindBlock(BlockNode):
    pass

class ReadBlock(BlockNode):
    pass

class RepeatBlock(BlockNode):
    pass

class IfBlock(BlockNode):
    else_body: List[Any] = Field(default_factory=list)

class Pass1Module(BaseModel):
    module_name: str
    statements: List[Any] = Field(default_factory=list)

class DecideBranchBlock(BlockNode):
    pass

class NoneBranchBlock(BlockNode):
    pass

class DecideBlock(BlockNode):
    branches: List[DecideBranchBlock] = Field(default_factory=list)
    none_branch: Optional[NoneBranchBlock] = None
