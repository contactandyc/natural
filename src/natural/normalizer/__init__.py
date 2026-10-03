# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
#
# Maintainer: Andy Curtis <contactandyc@gmail.com>

"""Natural-to-Semantic-IR parser and normalization framework."""

from natural.normalizer.pass1_parser import Pass1Parser
from natural.normalizer.pass2_dispatcher import Pass2Dispatcher
from natural.normalizer.preprocessor import NaturalPreprocessor
from natural.normalizer.schema_builder import SchemaBuilder
from natural.ir.serializer import serialize_to_yaml

__version__ = "0.1.0"
__all__ = [
    "Pass1Parser",
    "Pass2Dispatcher",
    "NaturalPreprocessor",
    "SchemaBuilder",
    "serialize_to_yaml",
]
