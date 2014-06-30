# encoding: utf-8
"""
refresh.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.open.capability import Capability
from exabgp.bgp.message.open.capability.id import CapabilityID

# ================================================================= RouteRefresh
#

class RouteRefresh (Capability):
	def __init__ (self):
		self.ID = CapabilityID.ROUTE_REFRESH

	def __str__ (self):
		if self.ID == CapabilityID.ROUTE_REFRESH:
			return 'Route Refresh'
		return 'Cisco Route Refresh'

	def extract (self):
		return ['']

	@staticmethod
	def unpack (capability,instance,data):
		# XXX: FIXME: we should set that that instance was seen and raise if seen twice
		return instance

RouteRefresh.register(CapabilityID.ROUTE_REFRESH)
RouteRefresh.register(CapabilityID.CISCO_ROUTE_REFRESH)


# ========================================================= EnhancedRouteRefresh
#

class EnhancedRouteRefresh (Capability):
	ID = CapabilityID.ENHANCED_ROUTE_REFRESH

	def __str__ (self):
		return 'Enhanced Route Refresh'

	def extract (self):
		return ['']

	@staticmethod
	def unpack (capability,instance,data):
		# XXX: FIXME: we should set that that instance was seen and raise if seen twice
		return instance

EnhancedRouteRefresh.register()
