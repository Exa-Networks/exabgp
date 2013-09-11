# encoding: utf-8
"""
refresh.py

Created by Thomas Mangin on 2012-07-19.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from struct import unpack,pack

from exabgp.protocol.family import AFI,SAFI
from exabgp.bgp.message import Message
from exabgp.bgp.message.notification import Notify

# =================================================================== Notification
# A Notification received from our peer.
# RFC 4271 Section 4.5

class RouteRefresh (Message):
	TYPE = chr(Message.Type.ROUTE_REFRESH)

	def __init__ (self):
		self._families = []

	def new (self,families):
		self._families = families
		return self

	def message (self,data):
		return self._message(
			''.join(['%s%s' % (pack('!H',afi),pack('!H',safi)) for (afi,safi) in self._families])
		)

	def factory (self,data):
		while len(data) >= 4:
			afi,safi = unpack('!HH',data[4:])
			self._families.append(AFI(afi),SAFI(safi))
		if data:
			raise Notify(2,0,'trailing data while parsing route-refresh')

	def __str__ (self):
		return "REFRESH"

	def extensive (self):
		return "route refresh %s" % ','.join(['%s %s' % (afi,safi) for (afi,safi) in self._families])

	def families (self):
		return self._families[:]
