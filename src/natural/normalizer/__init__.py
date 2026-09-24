# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
#
# Maintainer: Andy Curtis <contactandyc@gmail.com>

"""Natural-to-Semantic-IR parser and migration framework."""

from natural.normalizer.parser import NaturalParser
from natural.ir.serializer import serialize_to_yaml

__version__ = "0.1.0"
__all__ = ["NaturalParser", "serialize_to_yaml"]
