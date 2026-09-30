# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

"""Backward-compatibility shim for natural.codegen.python_emitter."""

from natural.codegen.targets.python.context import EmitterContext
from natural.codegen.targets.python.engine import PythonEmitter
from natural.codegen.targets.python.expressions import PythonExpressionEmitter
from natural.codegen.targets.python.formatters import convert_edit_mask, format_numeric_edit_mask
from natural.codegen.targets.python.harvester import ImportHarvester

__all__ = [
    "PythonEmitter",
    "EmitterContext",
    "PythonExpressionEmitter",
    "ImportHarvester",
    "convert_edit_mask",
    "format_numeric_edit_mask",
]
