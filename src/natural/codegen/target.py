# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import importlib
from abc import ABC, abstractmethod
from typing import Dict, List, Type
from natural.ir.models import DataAreaRef
from natural.ir.semantic import SemanticModule


class TargetBackend(ABC):
    """Abstract interface implemented by all language code generators."""

    target_name: str
    file_extension: str

    @abstractmethod
    def emit_module(self, module: SemanticModule, emit_main: bool = False) -> str:
        """Emits executable source code for an IR1 SemanticModule."""
        ...

    @abstractmethod
    def emit_schema(self, ddms: List[DataAreaRef]) -> Dict[str, str]:
        """Emits data schema / ORM files from DDMs.

        Returns a dictionary mapping relative file paths to file contents.
        Example: {"target_orm.py": "..."}
        """
        ...


TARGET_REGISTRY: Dict[str, Type[TargetBackend]] = {}


def register_target(name: str):
    """Decorator to register a target backend implementation."""
    def decorator(cls: Type[TargetBackend]):
        TARGET_REGISTRY[name.lower()] = cls
        return cls
    return decorator


def get_target(name: str = "python") -> TargetBackend:
    """Instantiates a target backend by name."""
    key = name.lower()
    if key not in TARGET_REGISTRY:
        # Dynamically import the target module to trigger @register_target
        importlib.import_module(f"natural.codegen.targets.{key}.target")

    cls = TARGET_REGISTRY.get(key)
    if not cls:
        available = ", ".join(sorted(TARGET_REGISTRY.keys()))
        raise ValueError(f"Unknown target '{name}'. Available targets: {available}")
    return cls()
