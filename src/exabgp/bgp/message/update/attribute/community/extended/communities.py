
"""communities.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.community.extended.community import ExtendedCommunity
from exabgp.bgp.message.update.attribute.community.extended.community import ExtendedCommunityIPv6
from exabgp.bgp.message.update.attribute.community.initial.communities import Communities

from exabgp.bgp.message.notification import Notify

# Extended Community size constants (RFC 4360, RFC 5701)
EXTENDED_COMMUNITY_SIZE = 8  # Standard extended community size
EXTENDED_COMMUNITY_IPV6_SIZE = 20  # IPv6 extended community size


# ===================================================== ExtendedCommunities (16)
# https://www.iana.org/assignments/bgp-extended-communities


@Attribute.register()
class ExtendedCommunities(Communities):
    ID = Attribute.CODE.EXTENDED_COMMUNITY

    @staticmethod
    def unpack(data, direction, negotiated):
        communities = ExtendedCommunities()
        while data:
            if data and len(data) < EXTENDED_COMMUNITY_SIZE:
                raise Notify(3, 1, 'could not decode extended community {}'.format(str([hex(_) for _ in data])))
            communities.add(ExtendedCommunity.unpack(data[:EXTENDED_COMMUNITY_SIZE], direction, negotiated))
            data = data[EXTENDED_COMMUNITY_SIZE:]
        return communities


# ===================================================== ExtendedCommunitiesIPv6 (25)
# RFC 5701


@Attribute.register()
class ExtendedCommunitiesIPv6(Communities):
    ID = Attribute.CODE.IPV6_EXTENDED_COMMUNITY

    @staticmethod
    def unpack(data, direction, negotiated):
        communities = ExtendedCommunitiesIPv6()
        while data:
            if data and len(data) < EXTENDED_COMMUNITY_IPV6_SIZE:
                raise Notify(3, 1, 'could not decode ipv6 extended community {}'.format(str([hex(_) for _ in data])))
            communities.add(ExtendedCommunityIPv6.unpack(data[:EXTENDED_COMMUNITY_IPV6_SIZE], direction, negotiated))
            data = data[EXTENDED_COMMUNITY_IPV6_SIZE:]
        return communities
