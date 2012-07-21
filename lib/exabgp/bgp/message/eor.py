# encoding: utf-8
"""
eor.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2010-2012 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message import Message
from exabgp.bgp.message.nlri.eor import RouteEOR,announcedRouteEOR

# =================================================================== End-Of-RIB
# not technically a different message type but easier to treat as one

class EOR (Message):
	TYPE = chr(0x02) # it is an update
	PREFIX = RouteEOR.PREFIX

	def __init__ (self):
		self.routes = []

	def new (self,families):
		for afi,safi in families:
			self.routes.append(RouteEOR(afi,safi,'announce'))
		return self

	def factory(self,data):
		self.routes.append(announcedRouteEOR(data))
		return self

	def updates (self,negociated):
		for eor in self.routes:
			yield self._message(eor.pack())

	def __str__ (self):
		return 'EOR'
