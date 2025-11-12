
"""hashtable.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, Optional


def _(key: str) -> str:
    return key.replace('_', '-')


class HashTable(dict[str, Any]):
    def __getitem__(self, key: str) -> Any:
        return dict.__getitem__(self, _(key))

    def __setitem__(self, key: str, value: Any) -> None:
        dict.__setitem__(self, _(key), value)

    def __getattr__(self, key: str) -> Any:
        return dict.__getitem__(self, _(key))

    def __setattr__(self, key: str, value: Any) -> None:
        dict.__setitem__(self, _(key), value)


class GlobalHashTable(HashTable):
    _instance: Optional[GlobalHashTable] = None

    def __new__(cls) -> GlobalHashTable:
        if cls._instance is None:
            cls._instance = super(GlobalHashTable, cls).__new__(cls)
        return cls._instance
