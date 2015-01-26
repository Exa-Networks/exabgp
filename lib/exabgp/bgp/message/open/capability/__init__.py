# encoding: utf-8
"""
capability/__init__.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.open.capability.capability import Capability

from exabgp.bgp.message.open.capability.addpath import AddPath
from exabgp.bgp.message.open.capability.asn4 import ASN4
from exabgp.bgp.message.open.capability.graceful import Graceful
from exabgp.bgp.message.open.capability.mp import MultiProtocol
from exabgp.bgp.message.open.capability.ms import MultiSession
from exabgp.bgp.message.open.capability.operational import Operational
from exabgp.bgp.message.open.capability.refresh import RouteRefresh
from exabgp.bgp.message.open.capability.refresh import EnhancedRouteRefresh
from exabgp.bgp.message.open.capability.unknown import UnknownCapability

# Must be imported and registered for the register API to work
Capability.register_capability(AddPath)
Capability.register_capability(ASN4)
Capability.register_capability(Graceful)
Capability.register_capability(MultiProtocol)
Capability.register_capability(MultiSession,Capability.CODE.MULTISESSION_CISCO)
Capability.register_capability(MultiSession,Capability.CODE.MULTISESSION)
Capability.register_capability(Operational)
Capability.register_capability(RouteRefresh,Capability.CODE.ROUTE_REFRESH)
Capability.register_capability(RouteRefresh,Capability.CODE.ROUTE_REFRESH_CISCO)
Capability.register_capability(EnhancedRouteRefresh)
Capability.fallback_capability(UnknownCapability)
# End registration


class REFRESH (object):
	ABSENT   = 0x01
	NORMAL   = 0x02
	ENHANCED = 0x04
