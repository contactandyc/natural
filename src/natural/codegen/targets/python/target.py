# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from pathlib import Path
from typing import Dict, List, Union
from natural.codegen.target import TargetBackend, register_target
from natural.codegen.targets.python.engine import PythonEmitter
from natural.codegen.targets.python.orm import FALLBACK_ORM_SOURCE, ORMEmitter
from natural.ir.models import DataAreaRef
from natural.ir.schema import SchemaCatalog
from natural.ir.semantic import SemanticModule
from natural.normalizer.schema_builder import SchemaBuilder


@register_target("python")
class PythonTarget(TargetBackend):
    target_name = "python"
    file_extension = ".py"

    def emit_module(self, module: SemanticModule, emit_main: bool = False) -> str:
        emitter = PythonEmitter(module)
        return emitter.generate(emit_main=emit_main)

    def emit_schema(self, schema_source: Union[SchemaCatalog, List[DataAreaRef]]) -> Dict[str, str]:
        if isinstance(schema_source, SchemaCatalog):
            catalog = schema_source
        else:
            catalog = SchemaBuilder(schema_source).build_catalog()

        if catalog.documents:
            orm_emitter = ORMEmitter(catalog)
            return {"target_orm.py": orm_emitter.generate()}
        return {"target_orm.py": FALLBACK_ORM_SOURCE}

    def emit_runtime(self) -> Dict[str, str]:
        runtime_dir = Path(__file__).parent / "runtime"
        outputs = {}
        if runtime_dir.is_dir():
            for p in runtime_dir.rglob("*.py"):
                rel = p.relative_to(runtime_dir)
                outputs[f"natural_runtime/{rel}"] = p.read_text(encoding="utf-8")
        return outputs
