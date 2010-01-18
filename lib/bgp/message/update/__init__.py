#!/usr/bin/env python
# encoding: utf-8
"""
update/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""


from bgp.utils import *
from bgp.structure.afi import AFI
from bgp.structure.safi import SAFI
from bgp.structure.ip import BGPPrefix
from bgp.structure.nlri import NLRIS
from bgp.message.parent import Message,prefix,defix

from bgp.message.update.parser import new_Attributes

# =================================================================== Update

def new_Update (data):
		length = len(data)
		# withdrawn
		lw,withdrawn,data = defix(data)
		if len(withdrawn) != lw:
			raise Notify(3,1)
		la,attribute,announced = defix(data)
		if len(attribute) != la:
			raise Notify(3,1)
		# The RFC check ...
		#if lw + la + 23 > length:
		if 2 + lw + 2+ la + len(announced) != length:
			raise Notify(3,1)

		remove = NLRIS()
		while withdrawn:
			nlri = BGPPrefix(AFI.ipv4,withdrawn)
			withdrawn = withdrawn[len(nlri):]
			remove.append(Update(nlri,'-'))

		attributes = new_Attributes(attribute)

		announce = NLRIS()
		while announced:
			nlri = BGPPrefix(AFI.ipv4,announced)
			announced = announced[len(nlri):]
			announce.append(nlri)

		return Update(remove,announce,attributes)

def to_Update (withdraw,nlri,attributes=None):
	return Update(withdraw,nlri,attributes)

class Update (Message):
	TYPE = chr(0x02)

	def __init__ (self,withdraw,nlri,attributes):
		self.nlri = nlri
		self.withdraw = withdraw
		if attributes == None:
			self.attributes = Attributes()
		else:
			self.attributes = attributes

	def announce (self,local_asn,remote_asn):
		nlri = ''.join([nlri.pack() for nlri in self.nlri])
		return self._message(prefix('') + prefix(self.attributes.bgp(local_asn,remote_asn)) + nlri)

	def withdraw (self,local_asn=None,remote_asn=None):
		withdraw = ''.join([withdraw.packedip() for withdraw in self.withdraw])
		nlri = ''.join([nlri.pack() for nlri in self.nlri])
		return self._message(prefix(withdraw) + prefix(''))

	def update (self,local_asn,remote_asn):
		withdraw = ''.join([withdraw.packedip() for withdraw in self.withdraw])
		nlri = ''.join([nlri.pack() for nlri in self.nlri])
		return self._message(prefix(withdraw) + prefix(self.attributes.bgp(local_asn,remote_asn)) + nlri)

	def added (self):
		routes = NLRIS()
		for nlri in self.nlri:
			r = Route(nlri)
			r.attributes = self.attributes
			routes.append(r)
		return routes

	def removed (self):
		nlris = NLRIS()
		for nlri in self.withdraw:
			nlris.append(nlri)
		return nlris

