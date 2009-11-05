#!/usr/bin/env python
# encoding: utf-8
"""
neighbor.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.message.open import HoldTime

HOLD_TIME = 180

# The definition of a neighbor (from reading the configuration)
class Neighbor (object):
	def __init__ (self):
		self.description = ''
		self._router_id = None
		self.local_address = None
		self.peer_address = None
		self.peer_as = None
		self.local_as = None
		self.hold_time = HoldTime(HOLD_TIME)
		self.routes = []

	def missing (self):
		if self.local_address is None: return 'local-address'
		if self.peer_address is None: return 'peer-address'
		if self.local_as is None: return 'local-as'
		if self.peer_as is None: return 'peer-as'
		if self.peer_address.version == 6 and not self._router_id: return 'router-id'
		return ''


	def get_router_id (self):
		return self._router_id if self._router_id else self.local_address
	def set_router_id (self,id):
		self._router_id = id
	router_id = property(get_router_id,set_router_id)

	def __eq__ (self,other):
		return \
			self._router_id == other._router_id and \
			self.local_address == other.local_address and \
			self.local_as == other.local_as and \
			self.peer_address == other.peer_address and \
			self.peer_as == other.peer_as

	def __ne__(self, other):
		return not (self == other)

	def __str__ (self):
		return """\
neighbor %s {
	description "%s";
	router-id %s;
	local-address %s;
	local-as %d;
	peer-as %d;
	static {%s
	}
}""" % (
	self.peer_address,
	self.description,
	self.router_id,
	self.local_address,
	self.local_as,
	self.peer_as,
	'\n\t\t' + '\n\t\t'.join([str(route) for route in self.routes]) if self.routes else ''
)
