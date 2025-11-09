
"""
Copyright (c) 2016 Job Snijders <job@ntt.net>
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.community.initial.communities import Communities
from exabgp.bgp.message.update.attribute.community.large.community import LargeCommunity

from exabgp.bgp.message.notification import Notify


@Attribute.register()
class LargeCommunities(Communities):
    ID = Attribute.CODE.LARGE_COMMUNITY

    @staticmethod
    def unpack(data, direction, negotiated):
        large_communities = LargeCommunities()
        while data:
            if data and len(data) < 12:
                raise Notify(3, 1, 'could not decode large community %s' % str([hex(_) for _ in data]))
            lc = LargeCommunity.unpack(data[:12], direction, negotiated)
            data = data[12:]
            if lc in large_communities.communities:
                continue
            large_communities.add(lc)
        return large_communities
