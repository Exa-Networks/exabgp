# encoding: utf-8
"""
mprnlri.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.protocol.ip import NoIP
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.ip.address import Address

from exabgp.bgp.message import IN
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.nlri.nlri import NLRI

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated


# ==================================================== MP Unreacheable NLRI (15)
#

class MPRNLRI (Attribute,Address):
	FLAG = Attribute.Flag.OPTIONAL
	ID = Attribute.CODE.MP_REACH_NLRI

	# __slots__ = ['nlris']

	def __init__ (self, afi, safi, nlris):
		Address.__init__(self,afi,safi)
		# all the routes must have the same next-hop
		self.nlris = nlris

	def packed_attributes (self, addpath, maximum):
		if not self.nlris:
			return

		mpnlri = {}
		for nlri in self.nlris:
			if nlri.nexthop is NoIP:
				# EOR and Flow may not have any next_hop
				nexthop = ''
			else:
				# we do not want a next_hop attribute packed (with the _attribute()) but just the next_hop itself
				if nlri.safi.has_rd():
					# .packed and not .pack()
					nexthop = chr(0)*8 + nlri.nexthop.packed
				else:
					# .packed and not .pack()
					nexthop = nlri.nexthop.packed

			# mpunli[afi,safi][nexthop] = nlri
			mpnlri.setdefault((nlri.afi.pack(),nlri.safi.pack()),{}).setdefault(nexthop,[]).append(nlri.pack(addpath))

		for (pafi,psafi),data in mpnlri.iteritems():
			for nexthop,nlris in data.iteritems():
				payload = \
					pafi + psafi + \
					chr(len(nexthop)) + nexthop + \
					chr(0) + ''.join(nlris)

				if self._len(payload) <= maximum:
					yield self._attribute(payload)
					continue

				# This will not generate an optimum update size..
				# we should feedback the maximum on each iteration

				for nlri in nlris:
					yield self._attribute(
						pafi + psafi +
						chr(len(nexthop)) + nexthop +
						chr(0) + nlri
					)

	def pack (self, addpath):
		return ''.join(self.packed_attributes(addpath,Negotiated.FREE_SIZE))

	def __len__ (self):
		raise RuntimeError('we can not give you the size of an MPRNLRI - was it with our witout addpath ?')
		# return len(self.pack(False))

	def __str__ (self):
		return "MP_REACH_NLRI for %s %s with %d NLRI(s)" % (self.afi,self.safi,len(self.nlris))

	@classmethod
	def unpack (cls, data, negotiated):
		nlris = []

		# -- Reading AFI/SAFI
		afi,safi = unpack('!HB',data[:3])
		offset = 3

		# we do not want to accept unknown families
		if negotiated and (afi,safi) not in negotiated.families:
			raise Notify(3,0,'presented a non-negotiated family %d/%d' % (afi,safi))

		# -- Reading length of next-hop
		len_nh = ord(data[offset])
		offset += 1

		rd = 0

		# check next-hope size
		if afi == AFI.ipv4:
			if safi in (SAFI.unicast,SAFI.multicast):
				if len_nh != 4:
					raise Notify(3,0,'invalid ipv4 unicast/multicast next-hop length %d expected 4' % len_nh)
			elif safi in (SAFI.mpls_vpn,):
				if len_nh != 12:
					raise Notify(3,0,'invalid ipv4 mpls_vpn next-hop length %d expected 12' % len_nh)
				rd = 8
			elif safi in (SAFI.flow_ip,):
				if len_nh not in (0,4):
					raise Notify(3,0,'invalid ipv4 flow_ip next-hop length %d expected 4' % len_nh)
			elif safi in (SAFI.flow_vpn,):
				if len_nh not in (0,4):
					raise Notify(3,0,'invalid ipv4 flow_vpn next-hop length %d expected 4' % len_nh)
		elif afi == AFI.ipv6:
			if safi in (SAFI.unicast,):
				if len_nh not in (16,32):
					raise Notify(3,0,'invalid ipv6 unicast next-hop length %d expected 16 or 32' % len_nh)
			elif safi in (SAFI.mpls_vpn,):
				if len_nh not in (24,40):
					raise Notify(3,0,'invalid ipv6 mpls_vpn next-hop length %d expected 24 or 40' % len_nh)
				rd = 8
			elif safi in (SAFI.flow_ip,):
				if len_nh not in (0,16,32):
					raise Notify(3,0,'invalid ipv6 flow_ip next-hop length %d expected 0, 16 or 32' % len_nh)
			elif safi in (SAFI.flow_vpn,):
				if len_nh not in (0,16,32):
					raise Notify(3,0,'invalid ipv6 flow_vpn next-hop length %d expected 0, 16 or 32' % len_nh)
		size = len_nh - rd

		# XXX: FIXME: GET IT FROM CACHE HERE ?
		nhs = data[offset+rd:offset+rd+size]
		nexthops = [nhs[pos:pos+16] for pos in range(0,len(nhs),16)]

		# chech the RD is well zero
		if rd and sum([int(ord(_)) for _ in data[offset:8]]) != 0:
			raise Notify(3,0,"MP_REACH_NLRI next-hop's route-distinguisher must be zero")

		offset += len_nh

		# Skip a reserved bit as somone had to bug us !
		reserved = ord(data[offset])
		offset += 1

		if reserved != 0:
			raise Notify(3,0,'the reserved bit of MP_REACH_NLRI is not zero')

		# Is the peer going to send us some Path Information with the route (AddPath)
		addpath = negotiated.addpath.receive(afi,safi)

		# Reading the NLRIs
		data = data[offset:]

		if not data:
			raise Notify(3,0,'No data to decode in an MPREACHNLRI but it is not an EOR %d/%d' % (afi,safi))

		while data:
			if nexthops:
				for nexthop in nexthops:
					length,nlri = NLRI.unpack(afi,safi,data,addpath,nexthop,IN.ANNOUNCED)
					nlris.append(nlri)
			else:
				length,nlri = NLRI.unpack(afi,safi,data,addpath,'',IN.ANNOUNCED)
				nlris.append(nlri)

			# logger.parser(LazyFormat("parsed announce mp nlri %s payload " % nlri,data[:length]))
			data = data[length:]
		return cls(afi,safi,nlris)

EMPTY_MPRNLRI  = MPRNLRI(AFI(AFI.undefined),SAFI(SAFI.undefined),[])
