# encoding: utf-8
"""
refresh.py

Created by Thomas Mangin on 2012-07-19.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import unpack
from struct import error

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message import Message
from exabgp.bgp.message.notification import Notify

# =================================================================== Notification
# A Notification received from our peer.
# RFC 4271 Section 4.5


class Reserved (int):
	def __str__ (self):
		if self == 0:
			return 'query'
		if self == 1:
			return 'begin'
		if self == 2:
			return 'end'
		return 'invalid'


class RouteRefresh (Message):
	ID = Message.CODE.ROUTE_REFRESH
	TYPE = chr(Message.CODE.ROUTE_REFRESH)

	request = 0
	start = 1
	end = 2

	def __init__ (self, afi, safi, reserved=0):
		self.afi = AFI(afi)
		self.safi = SAFI(safi)
		self.reserved = Reserved(reserved)

	def message (self):
		return self._message('%s%s%s' % (self.afi.pack(),chr(self.reserved),self.safi.pack()))

	def __str__ (self):
		return "REFRESH"

	def extensive (self):
		return 'route refresh %s/%d/%s' % (self.afi,self.reserved,self.safi)

	def families (self):
		return self._families[:]

	@classmethod
	def unpack_message (cls, data, _):
		try:
			afi,reserved,safi = unpack('!HBB',data)
		except error:
			raise Notify(7,1,'invalid route-refresh message')
		if reserved not in (0,1,2):
			raise Notify(7,2,'invalid route-refresh message subtype')
		return RouteRefresh(afi,safi,reserved)

	def __eq__ (self, other):
		if not isinstance(other, RouteRefresh):
			return False
		if self.afi != other.afi:
			return False
		if self.safi != other.safi:
			return False
		if self.reserved != other.reserved:
			return False
		return True
