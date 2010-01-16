#!/usr/bin/env python
# encoding: utf-8
"""
update/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""


from bgp.message.inet         import to_NLRI, new_NLRI, NLRI, to_IP, IP

from bgp.utils import *
from bgp.structure.afi import AFI
from bgp.structure.safi import SAFI
from bgp.structure.ip import to_Prefix
from bgp.message.parent import Message,prefix,defix

from bgp.message.update.parser import new_Attributes

from bgp.message.update.attribute.origin      import *	# 01
from bgp.message.update.attribute.aspath      import *	# 02
from bgp.message.update.attribute.nexthop     import *	# 03
from bgp.message.update.attribute.med         import * 	# 04
from bgp.message.update.attribute.localpref   import *	# 05
from bgp.message.update.attribute.aggregate   import *	# 06
from bgp.message.update.attribute.aggregator  import *	# 07
from bgp.message.update.attribute.communities import *	# 08
# 09
# 10 - 0A
# 11 - 0B
# 12 - 0C
# 13 - 0D
from bgp.message.update.attribute.mprnlri     import *	# 14 - 0E
from bgp.message.update.attribute.mpurnlri    import *	# 15 - 0F

# =================================================================== List of NLRI

class NLRIS (list):
	def __str__ (self):
		return "NLRIS %s" % str([str(nlri) for nlri in self])

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
			nlri = new_NLRI(withdrawn)
			withdrawn = withdrawn[len(nlri):]
			remove.append(Update(nlri,'-'))

		attributes = new_Attributes(attribute)

		announce = NLRIS()
		while announced:
			nlri = new_NLRI(announced)
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

	def pack_attributes (self,local_asn,peer_asn):
		ibgp = local_asn == peer_asn
		# we do not store or send MED
		message = ''

		attributes = [self.attributes[a].ID for a in self.attributes]

		if Attribute.ORIGIN in attributes:
			message += self.attributes[Attribute.ORIGIN].pack()
		elif self.attributes.autocomplete:
			message += Origin(Origin.IGP).pack()

		if Attribute.AS_PATH in attributes:
			message += self.attributes[Attribute.AS_PATH].pack()
		elif self.attributes.autocomplete:
			if local_asn == peer_asn:
				message += ASPath(ASPath.AS_SEQUENCE,[]).pack()
			else:
				message += ASPath(ASPath.AS_SEQUENCE,[local_asn]).pack()

		if Attribute.NEXT_HOP in attributes:
			message += self.attributes[Attribute.NEXT_HOP].pack()
#		XXX: This autocomplete SHOULD be uncessary and even possibly harmful
#		elif self.attributes.autocomplete:
#			message += to_NextHop('0.0.0.0').pack()

		if Attribute.LOCAL_PREFERENCE in attributes:
			if local_asn == peer_asn:
				message += self.attributes[Attribute.LOCAL_PREFERENCE].pack()

		if Attribute.MULTI_EXIT_DISC in attributes:
			if local_asn != peer_asn:
				message += self.attributes[Attribute.MULTI_EXIT_DISC].pack()

		for attribute in [Communities.ID,MPURNLRI.ID,MPRNLRI.ID]:
			if  self.attributes.has(attribute):
				message += self.attributes[attribute].pack()

		return message

	def announce (self,local_asn,remote_asn):
		attributes = self.pack_attributes(local_asn,remote_asn)
		nlri = ''.join([nlri.pack() for nlri in self.nlri])
		return self._message(prefix('') + prefix(attributes) + nlri)

	def withdraw (self,local_asn=None,remote_asn=None):
		withdraw = ''.join([withdraw.packedip() for withdraw in self.withdraw])
		attributes = self.pack_attributes(local_asn,remote_asn)
		nlri = ''.join([nlri.pack() for nlri in self.nlri])
		return self._message(prefix(withdraw) + prefix(''))

	def update (self,local_asn,remote_asn):
		withdraw = ''.join([withdraw.packedip() for withdraw in self.withdraw])
		attributes = self.pack_attributes(local_asn,remote_asn)
		nlri = ''.join([nlri.pack() for nlri in self.nlri])
		return self._message(prefix(withdraw) + prefix(attributes) + nlri)

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

