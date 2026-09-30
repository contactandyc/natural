# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import Any


class Tab:
    """Represents an absolute 1-based column position indicator."""
    __slots__ = ("col",)

    def __init__(self, col: int):
        self.col = int(col)


def tab(col: int) -> Tab:
    """Factory creating a column tab marker."""
    return Tab(col)


def tabulate(*items: Any) -> str:
    """Aligns strings and variable values to specified column tab stops."""
    buf = []
    curr_col = 0
    for it in items:
        if isinstance(it, Tab):
            target = max(0, it.col - 1)
            if target > curr_col:
                buf.append(" " * (target - curr_col))
                curr_col = target
        else:
            s = str(it)
            buf.append(s)
            curr_col += len(s)
    return "".join(buf)
