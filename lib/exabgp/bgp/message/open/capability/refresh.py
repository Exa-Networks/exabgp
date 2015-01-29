# encoding: utf-8
"""
refresh.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.open.capability.capability import Capability

# ================================================================= RouteRefresh
#


class RouteRefresh (Capability):
	def __init__ (self):
		self.ID = Capability.CODE.ROUTE_REFRESH

	def __str__ (self):
		if self.ID == Capability.CODE.ROUTE_REFRESH:
			return 'Route Refresh'
		return 'Cisco Route Refresh'

	def json (self):
		return '{ "name": "route-refresh", "variant": "%s" }' % ('RFC' if self.ID == Capability.CODE.ROUTE_REFRESH else 'Cisco')

	def extract (self):
		return ['']

	@staticmethod
	def unpack_capability (instance, data, capability=None):  # pylint: disable=W0613
		# XXX: FIXME: we should set that that instance was seen and raise if seen twice
		return instance

	def __eq__ (self, other):
		if not isinstance(other,RouteRefresh):
			return False
		return self.ID == other.ID


# ========================================================= EnhancedRouteRefresh
#


class EnhancedRouteRefresh (Capability):
	ID = Capability.CODE.ENHANCED_ROUTE_REFRESH

	def __str__ (self):
		return 'Enhanced Route Refresh'

	def json (self):
		return '{ "name": "enhanced-route-refresh" }'

	def extract (self):
		return ['']

	@staticmethod
	def unpack_capability (instance, data, capability=None):  # pylint: disable=W0613
		# XXX: FIXME: we should set that that instance was seen and raise if seen twice
		return instance
