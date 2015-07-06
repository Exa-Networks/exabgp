# encoding: utf-8
"""
nlri.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import unpack
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.ip.address import Address
from exabgp.protocol.ip import IP
from exabgp.bgp.message import IN
from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.nlri.cidr import CIDR

from exabgp.logger import Logger
from exabgp.logger import LazyFormat


class NLRI (Address):
	__slots__ = []

	EOR = False

	registered_nlri = dict()
	logger = None

	def __eq__ (self,other):
		return self.index() == other.index()

	def __ne__ (self,other):
		return not self.__eq__(other)

	def index (self):
		return '%s%s%s' % (self.afi,self.safi,self.pack())

	# remove this when code restructure is finished
	def pack (self, addpath=None):
		raise Exception('unimplemented')

	@staticmethod
	def register_nlri (klass, afi, safi):
		NLRI.registered_nlri['%d/%d' % (afi,safi)] = klass

	@classmethod
	def unpack (cls, afi, safi, data, addpath, nexthop, action):
		if not cls.logger:
			cls.logger = Logger()
		cls.logger.parser(LazyFormat("parsing %s/%s nlri payload " % (afi,safi),data))

		key = '%d/%d' % (afi,safi)
		if key in cls.registered_nlri:
			return cls.registered_nlri[key].unpack(afi,safi,data,addpath,nexthop,action)
		raise Notify(3,0,'trying to decode unknown family %s/%s' % (AFI(afi),SAFI(safi)))

	@staticmethod
	def _nlri (afi, safi, bgp, action, addpath):
		labels = []
		rd = ''

		if addpath:
			path_identifier = bgp[:4]
			bgp = bgp[4:]
		else:
			path_identifier = None

		mask = ord(bgp[0])
		bgp = bgp[1:]

		if SAFI(safi).has_label():
			while bgp and mask >= 8:
				label = int(unpack('!L',chr(0) + bgp[:3])[0])
				bgp = bgp[3:]
				mask -= 24  	# 3 bytes
				# The last 4 bits are the bottom of Stack
				# The last bit is set for the last label
				labels.append(label >> 4)
				# This is a route withdrawal
				if label == 0x800000 and action == IN.WITHDRAWN:
					break
				# This is a next-hop
				if label == 0x000000:
					break
				if label & 1:
					break

		if SAFI(safi).has_rd():
			mask -= 8*8  # the 8 bytes of the route distinguisher
			rd = bgp[:8]
			bgp = bgp[8:]

		if mask < 0:
			raise Notify(3,10,'invalid length in NLRI prefix')

		if not bgp and mask:
			raise Notify(3,10,'not enough data for the mask provided to decode the NLRI')

		size = CIDR.size(mask)

		if len(bgp) < size:
			raise Notify(3,10,'could not decode route with AFI %d sand SAFI %d' % (afi,safi))

		network,bgp = bgp[:size],bgp[size:]
		padding = '\0'*(IP.length(afi)-size)
		prefix = network + padding

		return labels,rd,path_identifier,mask,size,prefix,bgp
