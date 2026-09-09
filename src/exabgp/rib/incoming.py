"""store.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.protocol.family import FamilyTuple
from exabgp.rib.cache import Cache


class IncomingRIB(Cache):
    # The audit asks one question of each prefix: did the peer send more paths than the
    # limit we advertised. One path beyond the limit answers it, so that is as far as the
    # set has to grow. Without this a peer which ignores the limit, the only peer the audit
    # exists to catch, is also the one which decides how much memory the audit costs.
    AUDIT_PATHS_HEADROOM = 1

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

    def track_path(self, family: FamilyTuple, prefix_index: bytes, path_index: bytes, limit: int) -> int:
        """Record one received path and return how many this prefix now holds.

        The count saturates at one past `limit`. Past that point the audit has already
        warned about the prefix and the exact number would only cost memory, so a peer
        which keeps sending paths stops being able to grow this set. The trade is that
        once a prefix has saturated, withdrawals can take the count below what the peer
        actually holds, and a later violation on that prefix may go unreported.
        """
        assert limit > 0, 'a prefix is only audited against a limit we advertised'

        per_family = self._path_sets.setdefault(family, {})
        paths = per_family.setdefault(prefix_index, set())
        capacity = limit + self.AUDIT_PATHS_HEADROOM
        if len(paths) >= capacity and path_index not in paths:
            return len(paths)
        paths.add(path_index)
        assert len(paths) <= capacity, 'the audit set is bounded by the limit'
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
