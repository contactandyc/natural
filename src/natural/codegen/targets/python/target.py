# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import Dict, List
from natural.codegen.target import TargetBackend, register_target
from natural.codegen.targets.python.engine import PythonEmitter
from natural.codegen.targets.python.orm import FALLBACK_ORM_SOURCE, ORMEmitter
from natural.ir.models import DataAreaRef
from natural.ir.semantic import SemanticModule


@register_target("python")
class PythonTarget(TargetBackend):
    target_name = "python"
    file_extension = ".py"

    def emit_module(self, module: SemanticModule, emit_main: bool = False) -> str:
        emitter = PythonEmitter(module)
        return emitter.generate(emit_main=emit_main)

    def emit_schema(self, ddms: List[DataAreaRef]) -> Dict[str, str]:
        if ddms:
            orm_emitter = ORMEmitter(ddms)
            return {"target_orm.py": orm_emitter.generate()}
        return {"target_orm.py": FALLBACK_ORM_SOURCE}
