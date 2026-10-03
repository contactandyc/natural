# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import Any, List, Optional, Union


class KeyedArray(dict):
    """
    1-based and arbitrary-bounded dictionary container representing Natural array memory.
    Supports:
      - Integer keys: arr[1], arr[1990]
      - String keys: arr['1'], arr['1990']
      - Slices: arr[1:6] (key-range) or arr[0:6] (positional fallback)
      - Len, iteration, and serialization as standard JSON/dict
    """

    def __init__(self, *args, dim_start: int = 1, **kwargs):
        super().__init__()
        self.dim_start = dim_start
        if args:
            arg = args[0]
            if isinstance(arg, (list, tuple)):
                for i, v in enumerate(arg, start=dim_start):
                    self[str(i)] = self._wrap(v)
            elif isinstance(arg, dict):
                for k, v in arg.items():
                    self[str(k)] = self._wrap(v)
        for k, v in kwargs.items():
            self[str(k)] = self._wrap(v)

    @classmethod
    def _wrap(cls, v: Any) -> Any:
        if isinstance(v, (list, tuple)):
            return cls(v)
        elif isinstance(v, dict) and not isinstance(v, KeyedArray):
            return cls(v)
        return v

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, slice):
            vals = list(self.values())
            s_start = str(key.start) if key.start is not None else None
            s_stop = str(key.stop) if key.stop is not None else None
            if s_start is not None and s_start in self and s_stop is not None and s_stop in self:
                sub_keys = [k for k in self.keys() if int(s_start) <= int(k) <= int(s_stop)]
                return [self[k] for k in sub_keys]
            return vals[key]

        s_key = str(key)
        if s_key in self:
            val = super().__getitem__(s_key)
            if isinstance(val, (dict, list, tuple)) and not isinstance(val, KeyedArray):
                wrapped = self._wrap(val)
                super().__setitem__(s_key, wrapped)
                return wrapped
            return val

        if isinstance(key, int) and 0 <= key < len(self):
            vals = list(self.values())
            return vals[key]

        raise KeyError(key)

    def __setitem__(self, key: Any, val: Any) -> None:
        s_key = str(key)
        wrapped = self._wrap(val)
        super().__setitem__(s_key, wrapped)


def expand_array(arr: Any, size: int, fill: Any = None) -> Any:
    """Expands array or keyed dictionary to target size."""
    target_size = int(size)
    if isinstance(arr, (dict, KeyedArray)):
        for i in range(1, target_size + 1):
            k = str(i)
            if k not in arr:
                arr[k] = fill
        return arr
    if target_size > len(arr):
        arr.extend([fill] * (target_size - len(arr)))
    return arr


def reduce_array(arr: Any, size: int) -> Any:
    """Truncates array or keyed dictionary to target size."""
    target_size = int(size)
    if isinstance(arr, (dict, KeyedArray)):
        keys_to_del = [k for k in list(arr.keys()) if k.isdigit() and int(k) > target_size]
        for k in keys_to_del:
            del arr[k]
        return arr
    if target_size < len(arr):
        del arr[target_size:]
    return arr


def resize_array(arr: Any, size: int, fill: Any = None) -> Any:
    """Resizes array or keyed dictionary to target size."""
    target_size = int(size)
    if isinstance(arr, (dict, KeyedArray)):
        reduce_array(arr, target_size)
        expand_array(arr, target_size, fill=fill)
        return arr
    if target_size < len(arr):
        del arr[target_size:]
    elif target_size > len(arr):
        arr.extend([fill] * (target_size - len(arr)))
    return arr
