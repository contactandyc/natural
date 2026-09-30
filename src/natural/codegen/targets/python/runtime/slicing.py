# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import Any, Optional


def slice_assign(target: str, start: int, length: Optional[int], val: Any) -> str:
    """Performs 1-based offset and length slice mutation on an immutable string."""
    target = target or ""
    val_str = str(val) if val is not None else ""
    s = max(0, int(start) - 1)
    if len(target) < s:
        target = target.ljust(s)
    if length is None:
        return target[:s] + val_str
    e = s + int(length)
    return target[:s] + val_str + target[e:]
