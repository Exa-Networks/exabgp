"""
multicast.py

Created by Thomas Morin on 2014-06-23.
Copyright (c) 2014-2015 Orange. All rights reserved.
"""

from exabgp.protocol.ip import IP
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier import EthernetTag

from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN

# +---------------------------------------+
# |      RD   (8 octets)                  |
# +---------------------------------------+
# |  Ethernet Tag ID (4 octets)           |
# +---------------------------------------+
# |  IP Address Length (1 octet)          |
# +---------------------------------------+
# |   Originating Router's IP Addr        |
# |          (4 or 16 octets)             |
# +---------------------------------------+

# ===================================================================== EVPNNLRI


@EVPN.register
class Multicast (EVPN):
	CODE = 3
	NAME = "Inclusive Multicast Ethernet Tag"
	SHORT_NAME = "Multicast"

	def __init__ (self, rd, etag, ip, packed=None,nexthop=None,action=None,addpath=None):
		EVPN.__init__(self,packed,nexthop,action,addpath)
		# assert(isinstance(rd, RouteDistinguisher))
		# assert(isinstance(etag, EthernetTag))
		# assert(isinstance(ip, IP))
		self.rd = rd
		self.etag = etag
		self.ip = ip
		self._pack()

	def __ne__ (self, other):
		return not self.__eq__(other)

	def __str__ (self):
		return "%s:%s:%s:%s" % (
			self._prefix(),
			self.rd._str(),
			self.etag,
			self.ip,
		)

	def __hash__ (self):
		return hash((self.afi,self.safi,self.CODE,self.rd,self.etag,self.ip))

	def _pack (self):
		if not self._packed:
			ip = self.ip.pack()
			self._packed = '%s%s%s%s' % (
				self.rd.pack(),
				self.etag.pack(),
				chr(len(ip)*8),
				ip
			)
		return self._packed

	@classmethod
	def unpack (cls, data):
		rd = RouteDistinguisher.unpack(data[:8])
		etag = EthernetTag.unpack(data[8:12])
		iplen = ord(data[12])
		if iplen not in (4*8,16*8):
			raise Exception("IP len is %d, but EVPN route currently support only IPv4" % iplen)
		ip = IP.unpack(data[13:13+iplen/8])
		return cls(rd,etag,ip,data)
