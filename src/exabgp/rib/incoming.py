"""store.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.protocol.family import FamilyTuple
from exabgp.rib.cache import Cache


class IncomingRIB(Cache):
    _path_sets: dict[FamilyTuple, dict[bytes, set[bytes]]]
    _path_warned: set[tuple[FamilyTuple, bytes]]

    def __init__(self, cache: bool, families: set[FamilyTuple], enabled: bool = True) -> None:
        Cache.__init__(self, cache, families, enabled)
        self._path_sets = {}
        self._path_warned = set()

    # back to square one, all the routes are removed
    def clear(self) -> None:
        self.clear_cache()
        self._path_sets = {}
        self._path_warned = set()

    def reset(self) -> None:
        pass

    def track_path(self, family: FamilyTuple, prefix_index: bytes, path_index: bytes) -> int:
        per_family = self._path_sets.setdefault(family, {})
        paths = per_family.setdefault(prefix_index, set())
        paths.add(path_index)
        return len(paths)

    def untrack_path(self, family: FamilyTuple, prefix_index: bytes, path_index: bytes) -> None:
        per_family = self._path_sets.get(family)
        if per_family is None:
            return
        paths = per_family.get(prefix_index)
        if paths is None:
            return
        paths.discard(path_index)
        if not paths:
            per_family.pop(prefix_index, None)
            self._path_warned.discard((family, prefix_index))

    def path_count(self, family: FamilyTuple, prefix_index: bytes) -> int:
        per_family = self._path_sets.get(family)
        if per_family is None:
            return 0
        paths = per_family.get(prefix_index)
        return len(paths) if paths else 0

    def mark_warned(self, family: FamilyTuple, prefix_index: bytes) -> bool:
        key = (family, prefix_index)
        if key in self._path_warned:
            return False
        self._path_warned.add(key)
        return True
