# encoding: utf-8
"""
path.py

Created by Thomas Mangin on 2014-06-27.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.protocol.ip import IP
from exabgp.protocol.ip import NoNextHop
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message import IN
from exabgp.bgp.message import OUT
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.qualifier import PathInfo
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.notification import Notify


@NLRI.register(AFI.ipv4,SAFI.unicast)
@NLRI.register(AFI.ipv6,SAFI.unicast)
@NLRI.register(AFI.ipv4,SAFI.multicast)
@NLRI.register(AFI.ipv6,SAFI.multicast)
class INET (NLRI):
	__slots__ = ['path_info','cidr','nexthop','labels','rd']

	def __init__ (self, afi, safi, action=OUT.UNSET):
		NLRI.__init__(self,afi,safi,action)
		self.path_info = PathInfo.NOPATH
		self.cidr = CIDR.NOCIDR
		self.nexthop = NoNextHop

	def __len__ (self):
		return len(self.cidr) + len(self.path_info)

	def __repr__ (self):
		return self.extensive()

	def __eq__ (self, other):
		return \
			NLRI.__eq__(self, other) and \
			self.cidr == other.cidr and \
			self.path_info == other.path_info and \
			self.nexthop == other.nexthop

	def __ne__ (self, other):
		return not self.__eq__(other)

	def prefix (self):
		return "%s%s" % (self.cidr.prefix(),str(self.path_info))

	def pack (self, negotiated=None):
		addpath = self.path_info.pack() if negotiated and negotiated.addpath.send(self.afi,self.safi) else ''
		return addpath + self.cidr.pack_nlri()

	def index (self):
		addpath = 'no-pi' if self.path_info is PathInfo.NOPATH else self.path_info.pack()
		return addpath + self.cidr.pack_nlri()

	def extensive (self):
		return "%s%s" % (self.prefix(),'' if self.nexthop is NoNextHop else ' next-hop %s' % self.nexthop)

	def _internal (self,announced=True):
		return [self.path_info.json()]

	def json (self, announced=True):
		return '"%s": { %s }' % (self.cidr.prefix(),", ".join(self._internal(announced)))

	@classmethod
	def _pathinfo (cls, data, addpath):
		if addpath:
			return PathInfo(data[:4]),data[4:]
		return PathInfo.NOPATH, data

	# @classmethod
	# def unpack_inet (cls, afi, safi, data, action, addpath):
	# 	pathinfo, data = cls._pathinfo(data,addpath)
	# 	nlri,data = cls.unpack_range(data,action,addpath)
	# 	nlri.path_info = pathinfo
	# 	return nlri,data

	@classmethod
	def unpack_nlri (cls, afi, safi, bgp, action, addpath):
		nlri = cls(afi,safi,action)

		if addpath:
			nlri.path_info = PathInfo(bgp[:4])
			bgp = bgp[4:]

		mask = ord(bgp[0])
		bgp = bgp[1:]

		if cls.has_label():
			labels = []
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
			nlri.labels = Labels(labels)

		if cls.has_rd():
			mask -= 8*8  # the 8 bytes of the route distinguisher
			rd = bgp[:8]
			bgp = bgp[8:]
			nlri.rd = RouteDistinguisher(rd)

		if mask < 0:
			raise Notify(3,10,'invalid length in NLRI prefix')

		if not bgp and mask:
			raise Notify(3,10,'not enough data for the mask provided to decode the NLRI')

		size = CIDR.size(mask)

		if len(bgp) < size:
			raise Notify(3,10,'could not decode route with AFI %d sand SAFI %d' % (afi,safi))

		network,bgp = bgp[:size],bgp[size:]
		padding = '\0'*(IP.length(afi)-size)

		nlri.cidr = CIDR(network + padding,mask)

		return nlri,bgp
