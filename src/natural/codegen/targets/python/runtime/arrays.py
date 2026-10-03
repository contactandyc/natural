# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import Any, List, Optional, Union


class KeyedArray(dict):
    """
    1-based and arbitrary-bounded dictionary container representing Natural array memory.
    Supports integer/string keys, slices, and serialization as standard JSON/dict.
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
            s_start = str(key.start) if key.start is not None else None
            s_stop = str(key.stop) if key.stop is not None else None
            if isinstance(key.start, str) or isinstance(key.stop, str):
                try:
                    start_val = int(s_start) if s_start is not None else None
                    stop_val = int(s_stop) if s_stop is not None else None
                    sub_keys = [
                        k
                        for k in self.keys()
                        if (start_val is None or int(k) >= start_val)
                           and (stop_val is None or int(k) <= stop_val)
                    ]
                    return [self[k] for k in sub_keys]
                except (ValueError, TypeError):
                    pass
            vals = list(self.values())
            try:
                return vals[key]
            except TypeError:
                return vals

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


class AdabasArrayProxy:
    """
    Proxies a 1:Many child table relationship to act like a 1-based keyed dictionary.
    Mutations seamlessly append or update rows in the child collection.
    """

    def __init__(self, collection: Any, child_cls: Any, value_attr: str = "value"):
        self._collection = collection
        self._child_cls = child_cls
        self._value_attr = value_attr

    def _find_or_create(self, idx: Any) -> Any:
        try:
            target_idx = int(idx)
        except (ValueError, TypeError):
            target_idx = 1
        for row in self._collection:
            if getattr(row, "natural_index", None) == target_idx:
                return row
        new_row = self._child_cls(natural_index=target_idx)
        self._collection.append(new_row)
        return new_row

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, slice):
            s = sorted(self._collection, key=lambda r: getattr(r, "natural_index", 0))
            if isinstance(key.start, str) or isinstance(key.stop, str):
                try:
                    start_val = int(key.start) if key.start is not None else None
                    stop_val = int(key.stop) if key.stop is not None else None
                    return [
                        getattr(r, self._value_attr)
                        for r in s
                        if (start_val is None or getattr(r, "natural_index", 0) >= start_val)
                           and (stop_val is None or getattr(r, "natural_index", 0) <= stop_val)
                    ]
                except (ValueError, TypeError):
                    pass

            vals = [getattr(r, self._value_attr) for r in s]
            try:
                return vals[key]
            except TypeError:
                return vals

        try:
            target_idx = int(key)
        except (ValueError, TypeError):
            target_idx = None

        if target_idx is not None:
            for row in self._collection:
                if getattr(row, "natural_index", None) == target_idx:
                    return getattr(row, self._value_attr)

            # 0-based positional fallback
            if target_idx == 0:
                for row in self._collection:
                    if getattr(row, "natural_index", None) == 1:
                        return getattr(row, self._value_attr)

        return ""

    def __setitem__(self, key: Any, val: Any) -> None:
        row = self._find_or_create(key)
        setattr(row, self._value_attr, val)

    def __len__(self) -> int:
        return len(self._collection)

    def __iter__(self):
        for row in sorted(self._collection, key=lambda r: getattr(r, "natural_index", 0)):
            yield str(getattr(row, "natural_index", 0))

    def values(self) -> List[Any]:
        return [
            getattr(r, self._value_attr)
            for r in sorted(self._collection, key=lambda r: getattr(r, "natural_index", 0))
        ]

    def items(self):
        return [
            (str(getattr(r, "natural_index", 0)), getattr(r, self._value_attr))
            for r in sorted(self._collection, key=lambda r: getattr(r, "natural_index", 0))
        ]


class AdabasRowProxy:
    """Wraps a periodic child ORM row to allow both attribute and key access."""

    def __init__(self, row: Any):
        super().__setattr__("_row", row)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._row, name)

    def __setattr__(self, name: str, val: Any) -> None:
        if name == "_row":
            super().__setattr__(name, val)
        else:
            setattr(self._row, name, val)

    def __getitem__(self, key: Any) -> Any:
        return getattr(self._row, str(key))

    def __setitem__(self, key: Any, val: Any) -> None:
        setattr(self._row, str(key), val)


class AdabasObjectArrayProxy:
    """
    Proxies a Periodic Group (PE) child table relationship to act like a dictionary of row objects.
    """

    def __init__(self, collection: Any, child_cls: Any):
        self._collection = collection
        self._child_cls = child_cls

    def _find_or_create(self, idx: Any) -> Any:
        try:
            target_idx = int(idx)
        except (ValueError, TypeError):
            target_idx = 1
        for row in self._collection:
            if getattr(row, "natural_index", None) == target_idx:
                return row
        new_row = self._child_cls(natural_index=target_idx)
        self._collection.append(new_row)
        return new_row

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, slice):
            s = sorted(self._collection, key=lambda r: getattr(r, "natural_index", 0))
            if isinstance(key.start, str) or isinstance(key.stop, str):
                try:
                    start_val = int(key.start) if key.start is not None else None
                    stop_val = int(key.stop) if key.stop is not None else None
                    return [
                        AdabasRowProxy(r)
                        for r in s
                        if (start_val is None or getattr(r, "natural_index", 0) >= start_val)
                           and (stop_val is None or getattr(r, "natural_index", 0) <= stop_val)
                    ]
                except (ValueError, TypeError):
                    pass
            vals = [AdabasRowProxy(r) for r in s]
            try:
                return vals[key]
            except TypeError:
                return vals

        row = self._find_or_create(key)
        return AdabasRowProxy(row)

    def __setitem__(self, key: Any, val: Any) -> None:
        row = self._find_or_create(key)
        if isinstance(val, dict):
            for k, v in val.items():
                setattr(row, k, v)
        else:
            raise TypeError(f"Cannot assign non-dict {type(val)} to object array element")

    def __len__(self) -> int:
        return len(self._collection)

    def __iter__(self):
        for row in sorted(self._collection, key=lambda r: getattr(r, "natural_index", 0)):
            yield str(getattr(row, "natural_index", 0))

    def values(self) -> List[Any]:
        return [
            AdabasRowProxy(r)
            for r in sorted(self._collection, key=lambda r: getattr(r, "natural_index", 0))
        ]

    def items(self):
        return [
            (str(getattr(r, "natural_index", 0)), AdabasRowProxy(r))
            for r in sorted(self._collection, key=lambda r: getattr(r, "natural_index", 0))
        ]


def expand_array(arr: Any, size: int, fill: Any = None) -> Any:
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
