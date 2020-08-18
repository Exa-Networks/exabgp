# encoding: utf-8
"""
rib/__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.rib.incoming import IncomingRIB
from exabgp.rib.outgoing import OutgoingRIB


class RIB(object):

    # when we perform a configuration reload using SIGUSR, we must not use the RIB
    # without the cache, all the updates previously sent via the API are lost

    _cache = {}

    def __init__(self, name, adj_rib_in, adj_rib_out, families):
        self.name = name

        if name in self._cache:
            self.incoming = self._cache[name].incoming
            self.outgoing = self._cache[name].outgoing
            self.incoming.families = families
            self.outgoing.families = families
            self.outgoing.delete_cached_family(families)

            if adj_rib_out:
                self.outgoing.resend(None, False)
            else:
                self.outgoing.clear()
        else:
            self.incoming = IncomingRIB(adj_rib_in, families)
            self.outgoing = OutgoingRIB(adj_rib_out, families)
            self._cache[name] = self

    def reset(self):
        self.incoming.reset()
        self.outgoing.reset()

    def uncache(self):
        if self.name in self._cache:
            del self._cache[self.name]

    # This code was never tested ...
    def clear(self):
        self._cache[self.name].incoming = IncomingRIB(self.incoming.cache, self._cache[self.name].incoming.families)
        self._cache[self.name].outgoing = OutgoingRIB(self.outgoing.cache, self._cache[self.name].incoming.families)
