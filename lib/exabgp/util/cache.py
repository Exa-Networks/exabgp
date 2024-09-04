# encoding: utf-8
"""
cache.py

Created by David Farrar on 2012-12-27.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import time


class Cache(dict):
    def __init__(self, min_items=10, max_items=2000, cache_life=3600):
        dict.__init__(self)
        self.ordered = []
        self.min_items = min_items
        self.max_items = max_items
        self.cache_life = cache_life
        self.last_accessed = int(time.time())

    def cache(self, key, value):
        now = int(time.time())

        if now - self.last_accessed >= self.cache_life:
            self.truncate(self.min_items)

        elif len(self) >= self.max_items:
            self.truncate(self.max_items // 2)

        if key not in self:
            self.ordered.append(key)

        self.last_accessed = now
        self[key] = value

        return value

    def retrieve(self, key):
        now = int(time.time())
        res = self[key]

        if now - self.last_accessed >= self.cache_life:
            self.truncate(self.min_items)

            # only update the access time if we modified the cache
            self.last_accessed = now

        return res

    def truncate(self, pos):
        pos = len(self.ordered) - pos
        expiring = self.ordered[:pos]
        self.ordered = self.ordered[pos:]

        for _key in expiring:
            self.pop(_key)
