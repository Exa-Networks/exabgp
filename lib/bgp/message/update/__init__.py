#!/usr/bin/env python
# encoding: utf-8
"""
update/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""


from bgp.utils import *
from bgp.structure.address import AFI,SAFI
from bgp.structure.ip import BGPPrefix
from bgp.message import Message,prefix,defix

class NLRIS (list):
	def __str__ (self):
		return "NLRIS %s" % str([str(nlri) for nlri in self])


# =================================================================== Update

class Update (Message):
	TYPE = chr(0x02)

	def __init__ (self,withdraw,nlris,attributes=None):
		self.nlris = nlris
		self.withdraw = withdraw
		if attributes == None:
			self.attributes = Attributes()
		else:
			self.attributes = attributes

	def announce (self,local_asn,remote_asn):
		nlri = ''.join([nlri.pack() for nlri in self.nlris])
		return self._message(prefix('') + prefix(self.attributes.bgp(local_asn,remote_asn)) + nlri)

	def update (self,local_asn,remote_asn):
		withdraw = ''.join([withdraw.packedip() for withdraw in self.withdraw])
		nlri = ''.join([nlri.pack() for nlri in self.nlris])
		return self._message(prefix(withdraw) + prefix(self.attributes.bgp(local_asn,remote_asn)) + nlri)

	def withdraw (self,local_asn=None,remote_asn=None):
		withdraw = ''.join([withdraw.packedip() for withdraw in self.withdraw])
		nlri = ''.join([nlri.pack() for nlri in self.nlris])
		return self._message(prefix(withdraw) + prefix(''))

	def added (self):
		routes = NLRIS()
		for nlri in self.nlris:
			print "routes - nlri", type(nlri), nlri
			r = Route(nlri)
			r.attributes = self.attributes
			routes.append(r)
		return routes

	def removed (self):
		nlris = NLRIS()
		for nlri in self.withdraw:
			nlris.append(nlri)
		return nlris

