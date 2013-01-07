# encoding: utf-8
"""
neighbor.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from copy import copy

from exabgp.protocol.family import AFI
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.open.capability import AddPath
from exabgp.bgp.message.update.attribute.id import AttributeID

from exabgp.rib.watchdog import Watchdog

from exabgp.structure.log import Logger

# The definition of a neighbor (from reading the configuration)
class Neighbor (object):
	# This need to be global, all neighbor share the same data !
	# It allows us to use the information when performing global routing table update calculation
	watchdog = Watchdog()

	def __init__ (self):
		self.logger = Logger()
		self.description = ''
		self.router_id = None
		self.local_address = None
		self.peer_address = None
		self.peer_as = None
		self.local_as = None
		self.hold_time = HoldTime(180)
		self.asn4 = None
		self.add_path = 0
		self.md5 = None
		self.ttl = None
		self.group_updates = None

		# processes
		self.api_neighbor_changes = None
		self.api_received_updates = None
		self.api_received_routes = None

		# capability
		self.route_refresh = False
		self.graceful_restart = False
		self.multisession = None
		self.add_path = None

		self._families = []
		self._routes = {}

	def name (self):
		if self.multisession:
			session = "/ ".join("%s-%s" % (afi,safi) for (afi,safi) in self.families())
		else:
			session = 'in-open'
		return "%s local-ip %s family-allowed %s" % (self.peer_address,self.local_address,session)

	def families (self):
		# this list() is important .. as we use the function to modify self._families
		return list(self._families)

	def every_routes (self):
		for family in list(self._routes.keys()):
			for route in self._routes[family]:
				yield route

	def routes (self):
		# This function returns a hash and not a list as "in" tests are O(n) with lists and O(1) with hash
		# and with ten thousands routes this makes an enormous difference (60 seconds to 2)

		def _routes (self):
			for family in list(self._routes.keys()):
				for route in self._routes[family]:
					yield route

		routes = {}
		for route in self.watchdog.filtered(_routes(self)):
			routes[route.index()] = route
		return routes

	def add_family (self,family):
		if not family in self.families():
			self._families.append(family)

	def remove_family_and_routes (self,family):
		if family in self.families():
			self._families.remove(family)
			if family in self._routes:
				del self._routes[family]

	def add_route (self,route):
		self.watchdog.integrate(route)
		self._routes.setdefault((route.nlri.afi,route.nlri.safi),set()).add(route)

	def remove_route (self,route):
		try :
			routes = self._routes[(route.nlri.afi,route.nlri.safi)]
			if route.nlri.afi in (AFI.ipv4,AFI.ipv6):
				for r in list(routes):
					if r.nlri == route.nlri and \
					   r.attributes.get(AttributeID.NEXT_HOP,None) == route.attributes.get(AttributeID.NEXT_HOP,None):
						routes.remove(r)
						removed = True
			else:
				routes.remove(route)
				removed = True
		except KeyError:
			removed = False
		return removed

	def set_routes (self,routes):
		# routes can be a generator for self.everyroutes, if we delete self._families
		# then the generator will return an empty content when ran, so we can not use add_route
		f = {}
		for route in routes:
			f.setdefault((route.nlri.afi,route.nlri.safi),set()).add(route)
		self._routes = f

	def missing (self):
		if self.local_address is None: return 'local-address'
		if self.peer_address is None: return 'peer-address'
		if self.local_as is None: return 'local-as'
		if self.peer_as is None: return 'peer-as'
		if self.peer_address.afi == AFI.ipv6 and not self.router_id: return 'router-id'
		return ''

	# This function only compares the neighbor BUT NOT ITS ROUTES
	def __eq__ (self,other):
		return \
			self.router_id == other.router_id and \
			self.local_address == other.local_address and \
			self.local_as == other.local_as and \
			self.peer_address == other.peer_address and \
			self.peer_as == other.peer_as and \
			self.hold_time == other.hold_time and \
			self.md5 == other.md5 and \
			self.ttl == other.ttl and \
			self.route_refresh == other.route_refresh and \
			self.graceful_restart == other.graceful_restart and \
			self.multisession == other.multisession and \
			self.add_path == other.add_path and \
			self.group_updates == other.group_updates and \
			self.families() == other.families()

	def __ne__(self, other):
		return not (self == other)

	def __str__ (self):
		routes = ''
		for route in self.every_routes():
			routes += '\n    %s' % route

		families = ''
		for afi,safi in self.families():
			families += '\n    %s %s' % (afi.name(),safi.name())


		return """\
neighbor %s {
  description "%s";
  router-id %s;
  local-address %s;
  local-as %s;
  peer-as %s;
  hold-time %s;
%s%s%s
  capability {
%s%s%s%s%s  }
  family {%s
  }
  static { %s
  }
}""" % (
	self.peer_address,
	self.description,
	self.router_id,
	self.local_address,
	self.local_as,
	self.peer_as,
	self.hold_time,
	'  group-updates: %s;\n' % self.group_update if self.group_updates else '',
	'  md5: %d;\n' % self.ttl if self.ttl else '',
	'  ttl-security: %d;\n' % self.ttl if self.ttl else '',
	'    asn4 enable;\n' if self.asn4 else '    asn4 disable;\n',
	'    route-refresh;\n' if self.route_refresh else '',
	'    graceful-restart %s;\n' % self.graceful_restart if self.graceful_restart else '',
	'    add-path %s;\n' % AddPath.string[self.add_path] if self.add_path else '',
	'    multi-session;\n' if self.multisession else '',
	families,
	routes
)
