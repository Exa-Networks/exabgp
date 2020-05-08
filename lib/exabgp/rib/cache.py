# encoding: utf-8
"""
store.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.bgp.message import IN
from exabgp.bgp.message import OUT


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

    def cached_changes(self, families=None):
        # families can be None or []
        requested_families = self.families if families is None else set(families).intersection(self.families)

        # we use list() to make a snapshot of the data at the time we run the command
        for family in requested_families:
            for change in self._seen.get(family, {}).values():
                if change.nlri.action == OUT.ANNOUNCE:
                    yield change

    def is_cached(self, change):
        if not self.cache:
            return False
        # if we cache sent NLRI and this NLRI was never sent before, we do not need to send a withdrawal
        # as the route removed before we could announce it
        return change.index() not in self._seen.get(change.nlri.family(), {})

    # return a tuple exists in cache, same in cache
    def in_cache(self, change):
        if not self.cache:
            return False, False

        old_change = self._seen.get(change.nlri.family(), {}).get(change.index(), None)
        if not old_change:
            return False, False

        if change.nlri.action != OUT.ANNOUNCE:
            return True, False

        if old_change.attributes.index() != change.attributes.index():
            return True, False

        if old_change.nlri.nexthop.index() != change.nlri.nexthop.index():
            return True, False

        return True, True

    # add a change to the cache of seen Change
    def update_cache(self, change):
        if not self.cache:
            return
        family = change.nlri.family()
        index = change.index()
        if change.nlri.action == OUT.ANNOUNCE:
            self._seen.setdefault(family, {})[index] = change
        elif family in self._seen:
            self._seen[family].pop(index, None)
