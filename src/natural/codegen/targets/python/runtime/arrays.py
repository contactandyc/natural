# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import Any, List


def expand_array(arr: List[Any], size: int, fill: Any = None) -> List[Any]:
    """Expands array to target size, appending fill value without truncating."""
    target_size = int(size)
    if target_size > len(arr):
        arr.extend([fill] * (target_size - len(arr)))
    return arr


def reduce_array(arr: List[Any], size: int) -> List[Any]:
    """Truncates array to target size if larger."""
    target_size = int(size)
    if target_size < len(arr):
        del arr[target_size:]
    return arr


def resize_array(arr: List[Any], size: int, fill: Any = None) -> List[Any]:
    """Resizes array to target size, extending or truncating as needed."""
    target_size = int(size)
    if target_size < len(arr):
        del arr[target_size:]
    elif target_size > len(arr):
        arr.extend([fill] * (target_size - len(arr)))
    return arr
