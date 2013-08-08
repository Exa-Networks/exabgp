# encoding: utf-8
"""
update/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI,SAFI
from exabgp.protocol.ip.address import Address

from exabgp.bgp.message import Message,prefix
from exabgp.bgp.message.update.attribute.id import AttributeID as AID
from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI


# =================================================================== Update

class Update (Message):
	TYPE = chr(0x02)

	def new (self,nlris,attributes):
		self.nlris = nlris
		self.attributes = attributes
		return self

	def make_message(self,msg_size,attr,packed_mp,packed_nlri):
		packed = self._message(prefix('') + prefix(attr + ''.join(packed_mp)) + ''.join(packed_nlri))
		if len(packed) <= msg_size:
			yield packed
			return
		for packed in self.make_mesage(msg_size,attr,packed_mp[:len(packed_mp)/2],packed_nlri[:len(packed_nlri)/2]):
			yield packed
		for packed in self.make_mesage(msg_size,attr,packed_mp[len(packed_mp)/2:],packed_nlri[len(packed_nlri)/2:]):
			yield


	# The routes MUST have the same attributes ...
	def announce (self,negotiated,nlris=None,mps=None):
		asn4 = negotiated.asn4
		local_as = negotiated.local_as
		peer_as = negotiated.peer_as
		msg_size = negotiated.msg_size

		attr = self.attributes.pack(asn4,local_as,peer_as)

		if nlris is None and mps is None:
			packed_nlri = []
			packed_mp = []

			for nlri in self.nlris:
				afi,safi = nlri.afi,nlri.safi
				addpath = negotiated.addpath.send(afi,safi)

				if nlri.family() in negotiated.families:
					if afi == AFI.ipv4 and safi in [SAFI.unicast, SAFI.multicast] and nlri.nexthop == self.attributes.get(AID.NEXT_HOP,None):
						packed_nlri.append(nlri)
					else:
						packed_mp.append(nlri)
		else:
			packed_nlri = nlris
			packed_mp = mps

		if not packed_nlri and not packed_mp:
			return ''

		# XXX: FIXME: we should be able to use the generator
		return [_ for _ in self.make_message(msg_size,attr,MPRNLRI(packed_mp).pack(addpath),''.join(nlri.pack(addpath) for nlri in packed_nlri))]

	# def announce (self,negotiated):
	# 	asn4 = negotiated.asn4
	# 	local_as = negotiated.local_as
	# 	peer_as = negotiated.peer_as
	# 	msg_size = negotiated.msg_size
	# 	addpath = negotiated.addpath.send(self.afi,self.safi)

	# 	if self.afi == AFI.ipv4 and self.safi in [SAFI.unicast, SAFI.multicast]:
	# 		nlri = ''.join([route.nlri.pack(addpath) for route in self.routes if route.nlri.family() in negotiated.families])
	# 		mp = ''
	# 	else:
	# 		nlri = ''
	# 		if self.routes[0].nlri.family() in negotiated.families:
	# 			mp = MPRNLRI(self.routes).pack(addpath)
	# 		else:
	# 			mp = ''

	# 	if not nlri and not mp:
	# 		return ''

	# 	attr = self.attributes.pack(asn4,local_as,peer_as)
	# 	packed = self._message(prefix('') + prefix(attr + mp) + nlri)
	# 	if len(packed) > msg_size:
	# 		routes = self.routes
	# 		left = self.routes[:len(self.routes)/2]
	# 		right = self.routes[len(self.routes)/2:]
	# 		packed = []
	# 		self.routes = left
	# 		packed.extend(self.announce(negotiated))
	# 		self.routes = right
	# 		packed.extend(self.announce(negotiated))
	# 		self.routes = routes
	# 		return packed
	# 	return [packed]


	def withdraw (self,negotiated=None):
		if negotiated:
			#asn4 = negotiated.asn4
			#local_as = negotiated.local_as
			#peer_as = negotiated.peer_as
			addpath = negotiated.addpath.send(self.afi,self.safi)
			msg_size = negotiated.msg_size
		else:
			#asn4 = False
			#local_as = None
			#peer_as = None
			addpath = False
			msg_size = 4077

		if self.afi == AFI.ipv4 and self.safi in [SAFI.unicast, SAFI.multicast]:
			nlri = ''.join([route.nlri.pack(addpath) for route in self.routes])
			mp = ''
		else:
			nlri = ''
			mp = MPURNLRI(self.routes).pack(addpath)
		# last sentence of RFC 4760 Section 4, no attributes are required (and make sense)
		packed = self._message(prefix(nlri) + prefix(mp))
		if len(packed) > msg_size:
			routes = self.routes
			left = self.routes[:len(self.routes)/2]
			right = self.routes[len(self.routes)/2:]
			packed = []
			self.routes = left
			packed.extend(self.withdraw(negotiated))
			self.routes = right
			packed.extend(self.withdraw(negotiated))
			self.routes = routes
			return packed
		return [packed]

	def extensive (self,number):
		nlri = self.nlris[number]
		return "%s %s%s" % (str(Address(nlri.afi,nlri.safi)),str(nlri),str(self.attributes))

	def index (self,number):
		nlri = self.nlris[number]
		return nlri.pack(True)+nlri.rd.rd

	def __str__ (self):
		print "\n\nTO REMOVE\n\n"
		return '\n'.join([self.extensive(_) for _ in range(len(self.nlris))])
