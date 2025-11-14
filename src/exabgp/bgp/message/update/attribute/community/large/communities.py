"""Copyright (c) 2016 Job Snijders <job@ntt.net>
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.community.initial.communities import Communities
from exabgp.bgp.message.update.attribute.community.large.community import LargeCommunity

from exabgp.bgp.message.notification import Notify

# Large community size constant
LARGE_COMMUNITY_SIZE = (
    12  # Each large community is 12 bytes (4 bytes global admin + 4 bytes local data 1 + 4 bytes local data 2)
)


@Attribute.register()
class LargeCommunities(Communities):
    ID = Attribute.CODE.LARGE_COMMUNITY

    @staticmethod
    def unpack(data: bytes, direction: Any, negotiated: Negotiated) -> LargeCommunities:
        large_communities = LargeCommunities()
        while data:
            if data and len(data) < LARGE_COMMUNITY_SIZE:
                raise Notify(3, 1, 'could not decode large community {}'.format(str([hex(_) for _ in data])))
            lc = LargeCommunity.unpack(data[:LARGE_COMMUNITY_SIZE], direction, negotiated)
            data = data[LARGE_COMMUNITY_SIZE:]
            if lc in large_communities.communities:
                continue
            large_communities.add(lc)  # type: ignore[arg-type]
        return large_communities
