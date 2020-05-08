# encoding: utf-8
"""
community.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# ============================================================== Communities (8)
# https://www.iana.org/assignments/bgp-extended-communities

from exabgp.util import ordinal
from exabgp.util import concat_bytes_i

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.community.initial.community import Community

from exabgp.bgp.message.notification import Notify


@Attribute.register()
class Communities(Attribute):
    ID = Attribute.CODE.COMMUNITY
    FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL

    # __slots__ = ['communities']

    def __init__(self, communities=None):
        # Must be None as = param is only evaluated once
        if communities:
            self.communities = communities
        else:
            self.communities = []

    def add(self, data):
        self.communities.append(data)
        return self

    def pack(self, negotiated=None):
        if len(self.communities):
            return self._attribute(concat_bytes_i(c.pack() for c in self.communities))
        return b''

    def __iter__(self):
        return iter(self.communities)

    def __repr__(self):
        lc = len(self.communities)
        if lc > 1:
            return "[ %s ]" % " ".join(repr(community) for community in sorted(self.communities))
        if lc == 1:
            return repr(self.communities[0])
        return ""

    def json(self):
        return "[ %s ]" % ", ".join(community.json() for community in self.communities)

    @staticmethod
    def unpack(data, negotiated):
        communities = Communities()
        while data:
            if data and len(data) < 4:
                raise Notify(3, 1, 'could not decode community %s' % str([hex(ordinal(_)) for _ in data]))
            communities.add(Community.unpack(data[:4], negotiated))
            data = data[4:]
        return communities
