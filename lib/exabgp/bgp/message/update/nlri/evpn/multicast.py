"""
multicast.py

Created by Thomas Morin on 2014-06-23.
Copyright (c) 2014-2015 Orange. All rights reserved.
"""

from exabgp.protocol.ip import IP
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier.etag import EthernetTag

from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN


# ===================================================================== EVPNNLRI

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

class Multicast (EVPN):
	CODE = 3
	NAME = "Inclusive Multicast Ethernet Tag"
	SHORT_NAME = "Multicast"

	def __init__ (self, rd, etag, ip):
		self.rd = rd
		self.etag = etag
		self.ip = ip
		EVPN.__init__(self,self.pack())

	def __str__ (self):
		return "%s:%s:%s:%s" % (
			self._prefix(),
			self.rd,
			self.etag,
			self.ip,
		)

	def __cmp__ (self, other):
		if not isinstance(other,self.__class__):
			return -1
		if self.rd != other.rd:
			return -1
		if self.etag != other.etag:
			return -1
		if self.ip != other.ip:
			return -1
		return 0

	# XXX: FIXME: improve for better performance?
	def __hash__ (self):
		return hash("%s:%s:%s:%s:%s:%s" % (self.afi,self.safi,self.CODE,self.rd,self.etag,self.ip))

	def pack (self):
		ip = self.ip.pack()
		return '%s%s%s%s' % (
			self.rd.pack(),
			self.etag.pack(),
			chr(len(ip)*8),
			ip
		)

	@classmethod
	def unpack (cls, data):
		rd = RouteDistinguisher.unpack(data[:8])
		etag = EthernetTag.unpack(data[8:12])
		iplen = ord(data[12])*8
		ip = IP.unpack(data[12:12+iplen])
		if iplen not in (4*8,16*8):
			raise Exception("IP len is %d, but EVPN route currently support only IPv4" % iplen)
		return cls(rd,etag,ip)
