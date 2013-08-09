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


	# The routes MUST have the same attributes ...
	def announce (self,negotiated):
		asn4 = negotiated.asn4
		local_as = negotiated.local_as
		peer_as = negotiated.peer_as
		msg_size = negotiated.msg_size

		attr = self.attributes.pack(asn4,local_as,peer_as)

		all_nlri = []
		sorted_mp = {}

		for nlri in self.nlris:
			if nlri.family() in negotiated.families:
				if nlri.afi == AFI.ipv4 and nlri.safi in [SAFI.unicast, SAFI.multicast] and nlri.nexthop == self.attributes.get(AID.NEXT_HOP,None):
					all_nlri.append(nlri)
				else:
					sorted_mp.setdefault((nlri.afi,nlri.safi),[]).append(nlri)

		if not all_nlri and not sorted_mp:
			return

		msg_size = msg_size - 2 - 2 - len(attr)  # 2 bytes for each prefix() header

		packed_mp = ''
		packed_nlri = ''

		families = sorted_mp.keys()
		while families:
			family = families.pop()
			mps = sorted_mp[family]
			addpath = negotiated.addpath.send(*family)
			mp_packed_generator = MPRNLRI(mps).packed_attributes(addpath)
			try:
				while True:
					packed = mp_packed_generator.next()
					if len(packed_mp + packed) > msg_size:
						yield self._message(prefix('') + prefix(attr + packed_mp))
						packed_mp = packed
					else:
						packed_mp += packed
			except StopIteration:
				pass

		addpath = negotiated.addpath.send(AFI.ipv4,SAFI.unicast)
		while all_nlri:
			nlri = all_nlri.pop()
			packed = nlri.pack(addpath)
			if len(packed_mp + packed_nlri + packed) > msg_size:
				yield self._message(prefix('') + prefix(attr + packed_mp) + packed_nlri)
				packed_mp = ''
				packed_nlri = packed
			else:
				packed_nlri += packed

		if packed_mp or packed_nlri:
			yield self._message(prefix('') + prefix(attr + packed_mp) + packed_nlri)


	def withdraw (self,negotiated=None):
		msg_size = negotiated.msg_size

		#packed_nlri = {}
		#packed_mp = {}

		all_nlri = []
		sorted_mp = {}

		for nlri in self.nlris:
			if nlri.family() in negotiated.families:
				if nlri.afi == AFI.ipv4 and nlri.safi in [SAFI.unicast, SAFI.multicast]:
					all_nlri.append(nlri)
				else:
					sorted_mp.setdefault((nlri.afi,nlri.safi),[]).append(nlri)

		if not all_nlri and not sorted_mp:
			return

		msg_size = msg_size - 2  # 2 bytes for the prefix() header

		packed_mp = ''
		packed_nlri = ''

		addpath = negotiated.addpath.send(AFI.ipv4,SAFI.unicast)

		while all_nlri:
			nlri = all_nlri.pop()
			packed = nlri.pack(addpath)
			if len(packed_nlri + packed) > msg_size:
				yield self._message(prefix(packed_nlri))
				packed_nlri = packed
			else:
				packed_nlri += packed


		families = sorted_mp.keys()
		while families:
			family = families.pop()
			mps = sorted_mp[family]
			addpath = negotiated.addpath.send(*family)
			mp_packed_generator = MPURNLRI(mps).packed_attributes(addpath)
			try:
				while True:
					packed = mp_packed_generator.next()
					if len(packed_nlri + packed_mp + packed) > msg_size:
						if packed_mp:
							yield self._message(prefix(packed_nlri) + prefix(packed_mp))
						else:
							yield self._message(prefix(packed_nlri))
						packed_nlri = ''
						packed_mp = packed
					else:
						packed_mp += packed
			except StopIteration:
				pass

		if packed_mp:
			yield self._message(prefix(packed_nlri) + prefix(packed_mp))
		else:
			yield self._message(prefix('') + prefix(packed_nlri))


	def extensive (self,number):
		nlri = self.nlris[number]
		return "%s %s%s" % (str(Address(nlri.afi,nlri.safi)),str(nlri),str(self.attributes))

	def index (self,number):
		nlri = self.nlris[number]
		return nlri.pack(True)+nlri.rd.rd

	def __str__ (self):
		print "\n\nTO REMOVE\n\n"
		return '\n'.join([self.extensive(_) for _ in range(len(self.nlris))])
