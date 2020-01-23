# encoding: utf-8
"""
__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# Every Extended Community should be imported from this file
# as it makes sure that all the registering decorator are run

from exabgp.bgp.message.update.attribute.community.extended.community import ExtendedCommunity
from exabgp.bgp.message.update.attribute.community.extended.community import ExtendedCommunityIPv6
from exabgp.bgp.message.update.attribute.community.extended.communities import ExtendedCommunities
from exabgp.bgp.message.update.attribute.community.extended.communities import ExtendedCommunitiesIPv6

from exabgp.bgp.message.update.attribute.community.extended.l2info import L2Info
from exabgp.bgp.message.update.attribute.community.extended.origin import Origin
from exabgp.bgp.message.update.attribute.community.extended.origin import OriginASNIP
from exabgp.bgp.message.update.attribute.community.extended.origin import OriginIPASN
from exabgp.bgp.message.update.attribute.community.extended.origin import OriginASN4Number
from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTarget
from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTargetASN2Number
from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTargetIPNumber
from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTargetASN4Number
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficRate
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficAction
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficRedirect
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficRedirectASN4
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficMark
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficRedirectIPv6
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficNextHopIPv4IETF
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficNextHopIPv6IETF
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficNextHopSimpson
from exabgp.bgp.message.update.attribute.community.extended.encapsulation import Encapsulation
from exabgp.bgp.message.update.attribute.community.extended.chso import ConsistentHashSortOrder
from exabgp.bgp.message.update.attribute.community.extended.rt_record import RTRecord
from exabgp.bgp.message.update.attribute.community.extended.flowspec_scope import InterfaceSet
from exabgp.bgp.message.update.attribute.community.extended.mac_mobility import MacMobility
