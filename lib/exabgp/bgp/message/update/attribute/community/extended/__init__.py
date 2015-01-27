# encoding: utf-8
"""
community.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update.attribute.community.extended.community import ExtendedCommunity

from exabgp.bgp.message.update.attribute.community.extended.encapsulation import Encapsulation
from exabgp.bgp.message.update.attribute.community.extended.l2info import L2Info
from exabgp.bgp.message.update.attribute.community.extended.origin import OriginASNIP
from exabgp.bgp.message.update.attribute.community.extended.origin import OriginIPASN
from exabgp.bgp.message.update.attribute.community.extended.origin import OriginASN4Number
from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTargetASNIP
from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTargetIPASN
from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTargetASN4Number
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficRate
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficAction
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficRedirect
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficMark
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficNextHop

ExtendedCommunity.register_extended(Encapsulation)
ExtendedCommunity.register_extended(L2Info)

ExtendedCommunity.register_extended(OriginASNIP)
ExtendedCommunity.register_extended(OriginIPASN)
ExtendedCommunity.register_extended(OriginASN4Number)

ExtendedCommunity.register_extended(RouteTargetASNIP)
ExtendedCommunity.register_extended(RouteTargetIPASN)
ExtendedCommunity.register_extended(RouteTargetASN4Number)

ExtendedCommunity.register_extended(TrafficRate)
ExtendedCommunity.register_extended(TrafficAction)
ExtendedCommunity.register_extended(TrafficRedirect)
ExtendedCommunity.register_extended(TrafficMark)
ExtendedCommunity.register_extended(TrafficNextHop)
