# encoding: utf-8
"""
refresh.py

Created by Thomas Mangin on 2012-07-19.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.protocol.family import AFI,SAFI
from exabgp.bgp.message import Failure, Message
from exabgp.bgp.message.notification import Notify

# =================================================================== Notification
# A Notification received from our peer.
# RFC 4271 Section 4.5

class RouteRefresh (Message,Failure):
	TYPE = chr(0x05)

	def __init__ (self):
		self.families = []

	def new (self,families):
		self.families = families

	def factory (self,data):
		while len(data) >= 4:
			afi,safi = unpack('!HH',data[4:])
			self.families.append(AFI(afi),SAFI(safi))
		if data:
			raise Notify(2,0,'trailing data while parsing route-refresh')

	def __str__ (self):
		return "REFRESH"
