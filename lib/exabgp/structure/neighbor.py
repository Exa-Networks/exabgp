# encoding: utf-8
"""
neighbor.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

from copy import copy

from exabgp.structure.address import AFI
from exabgp.message.open import HoldTime
from exabgp.message.update.attribute.id import AttributeID

from exabgp.log import Logger
logger = Logger()

# The definition of a neighbor (from reading the configuration)
class Neighbor (object):
	def __init__ (self):
		self.description = ''
		self.router_id = None
		self.local_address = None
		self.peer_address = None
		self.peer_as = None
		self.local_as = None
		self.hold_time = HoldTime(180)
		self.graceful_restart = False
		self.md5 = None
		self.ttl = None
		self.multisession = None
		self.parse_routes = None
		self._families = {}
		self._watchdog = {}

	def name (self):
		if self.multisession:
			session =  ", ".join("%s %s" % (afi,safi) for (afi,safi) in self._families.keys())
			return "%s-%s multi-session %s" % (self.local_address,self.peer_address,session)
		else:
			return "%s-%s" % (self.local_address,self.peer_address)

	def families (self):
		return self._families.keys()

	def watchdog (self,watchdog):
		self._watchdog = copy(watchdog)

	def every_routes (self):
		for family in self._families:
			for route in self._families[family]:
				yield route

	def filtered_routes (self):
		# This function returns a hash and not a list as "in" tests are O(n) with lists and O(1) with hash
		# and with ten thousands routes this makes an enormous difference (60 seconds to 2)
		routes = {}
		for family in self._families:
			for route in self._families[family]:
				withdrawn = route.attributes.pop(AttributeID.INTERNAL_WITHDRAWN,None)
				if withdrawn is not None:
					logger.rib('skipping initial announcement of %s' % route)
					watchdog = route.attributes.get(AttributeID.INTERNAL_WATCHDOG,None)
					if watchdog in self._watchdog:
						self._watchdog[watchdog] == 'withdraw'
					continue
				watchdog = route.attributes.get(AttributeID.INTERNAL_WATCHDOG,None)
				if watchdog in self._watchdog:
					if self._watchdog[watchdog] == 'withdraw':
						continue
				routes[str(route)] = route
		return routes

	def remove_family (self,family):
		if family in self._families:
			del self._families[family]

	def add_route (self,route):
		self._families.setdefault((route.nlri.afi,route.nlri.safi),[]).append(route)

	def remove_route (self,route):
		result = False
		for r in self._families.get((route.nlri.afi,route.nlri.safi),[]):
			if r == route:
				self._families[(route.nlri.afi,route.nlri.safi)].remove(r)
				result = True
		return result

	def set_routes (self,routes):
		self._families = {}
		for route in routes:
			self.add_route(route)

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
			self.graceful_restart == other.graceful_restart and \
			self.md5 == other.md5 and \
			self.ttl == other.ttl and \
			self.multisession == other.multisession and \
			self.families() == other.families()

	def __ne__(self, other):
		return not (self == other)

	def __str__ (self):
		routes = '\n\t\t'
		for family in self._families:
			for _routes in self._families[family]:
				routes += '\n\t\t%s' % _routes

		options = []
		if self.md5: options.append("md5: %s;" % self.md5)
		if self.ttl is not None: options.append("ttl-security: %d;" % self.ttl)
		if self.graceful_restart: options.append("graceful-restart: %d;" % self.graceful_restart)

		return """\
neighbor %s {
	description "%s";
	router-id %s;
	local-address %s;
	local-as %s;
	peer-as %s;
	hold-time %s;
	%s
	static {%s
	}
}""" % (
	self.peer_address,
	self.description,
	self.router_id,
	self.local_address,
	self.local_as,
	self.peer_as,
	self.hold_time,
	'\n\t'.join(options),
	routes
)

	def __repr__ (self):
		return str(self)
