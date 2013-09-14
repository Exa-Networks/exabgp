# encoding: utf-8
"""
refresh.py

Created by Thomas Mangin on 2012-07-19.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.protocol.family import AFI,SAFI
from exabgp.bgp.message import Message

# =================================================================== Notification
# A Notification received from our peer.
# RFC 4271 Section 4.5

class RouteRefresh (Message):
	TYPE = chr(Message.Type.ROUTE_REFRESH)

	request = 0
	start = 1
	end = 2

	def __init__ (self,afi,safi,reserved=0):
		self.afi = AFI(afi)
		self.safi = SAFI(safi)
		self.reserved = reserved

	def messages (self,negotitated):
		return [self._message('%s%s%s' % (self.afi.pack(),chr(self.reserved),self.safi.pack())),]

	def __str__ (self):
		return "REFRESH"

	def extensive (self):
		return 'route refresh %s/%d/%s' % (self.afi,self.reserved,self.safi)

	def families (self):
		return self._families[:]

def RouteRefreshFactory (data):
	afi,reserved,safi = unpack('!HBB',data)
	return RouteRefresh(afi,safi,reserved)
