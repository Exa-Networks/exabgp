
"""
store.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.bgp.message import Action


class Cache(object):
    def __init__(self, cache, families):
        self.cache = cache
        self._seen = {}
        # self._seen[family][change-index] = change
        # nlri.index() would be a few bytes shorter than change.index() but ..
        # we need change.index() in other part of the code
        # we pre-compute change.index() so that it is only allocted once
        self.families = families

    def clear_cache(self):
        self._seen = {}

    def delete_cached_family(self, families):
        for family in self._seen.keys():
            if family not in families:
                del self._seen[family]

    def cached_changes(self, families=None, actions=[Action.ANNOUNCE]):
        # families can be None or []
        requested_families = self.families if families is None else set(families).intersection(self.families)

        # we use list() to make a snapshot of the data at the time we run the command
        for family in requested_families:
            for change in self._seen.get(family, {}).values():
                if change.nlri.action in actions:
                    yield change

    def in_cache(self, change):
        if not self.cache:
            return False

        if change.nlri.action == Action.WITHDRAW:
            return False

        cached = self._seen.get(change.nlri.family().afi_safi(), {}).get(change.index(), None)
        if not cached:
            return False

        if cached.attributes.index() != change.attributes.index():
            return False

        if cached.nlri.nexthop.index() != change.nlri.nexthop.index():
            return False

        return True

    # add a change to the cache of seen Change
    def update_cache(self, change):
        if not self.cache:
            return
        family = change.nlri.family().afi_safi()
        index = change.index()
        if change.nlri.action == Action.ANNOUNCE:
            self._seen.setdefault(family, {})[index] = change
        elif family in self._seen:
            self._seen[family].pop(index, None)
