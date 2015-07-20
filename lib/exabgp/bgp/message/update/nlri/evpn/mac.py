"""
mac.py

Created by Thomas Morin on 2014-06-23.
Copyright (c) 2014-2015 Orange. All rights reserved.
"""

from exabgp.protocol.ip import IP
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.qualifier import ESI
from exabgp.bgp.message.update.nlri.qualifier import EthernetTag
from exabgp.bgp.message.update.nlri.qualifier import MAC as MACQUAL

from exabgp.bgp.message.update.nlri import NLRI

from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN

from exabgp.bgp.message.notification import Notify

# +---------------------------------------+
# |      RD   (8 octets)                  |
# +---------------------------------------+
# |Ethernet Segment Identifier (10 octets)|
# +---------------------------------------+
# |  Ethernet Tag ID (4 octets)           |
# +---------------------------------------+
# |  MAC Address Length (1 octet)         |
# +---------------------------------------+
# |  MAC Address (6 octets)               |  48 bits is 6 bytes
# +---------------------------------------+
# |  IP Address Length (1 octet)          |  zero if IP Address field absent
# +---------------------------------------+
# |  IP Address (4 or 16 octets)          |
# +---------------------------------------+
# |  MPLS Label (3 octets)                |
# +---------------------------------------+

# ===================================================================== EVPNNLRI


@EVPN.register
class MAC (EVPN):
	CODE = 2
	NAME = "MAC/IP advertisement"
	SHORT_NAME = "MACAdv"

	def __init__ (self, rd, esi, etag, mac, maclen, label,ip,packed=None,nexthop=None,action=None,addpath=None):
		EVPN.__init__(self,packed,nexthop,action,addpath)
		# assert(isinstance(rd, RouteDistinguisher))
		# assert(isinstance(etag, EthernetTag))
		# assert(isinstance(ip, IP))
		# assert(isinstance(mac, MACQUAL))
		self.rd = rd
		self.esi = esi
		self.etag = etag
		self.maclen = maclen
		self.mac = mac
		self.ip = ip
		self.label = label if label else Labels.NOLABEL
		self._pack()

	def __eq__ (self, other):
		return \
			isinstance(other, MAC) and \
			self.CODE == other.CODE and \
			self.rd == other.rd and \
			self.etag == other.etag and \
			self.mac == other.mac and \
			self.ip == other.ip
		# esi and label must not be part of the comparaison

	def __ne__ (self, other):
		return not self.__eq__(other)

	def __str__ (self):
		return "%s:%s:%s:%s:%s%s:%s:%s" % (
			self._prefix(),
			self.rd._str(),
			self.esi,
			self.etag,
			self.mac,
			"" if len(self.mac) == 48 else "/%d" % self.maclen,
			self.ip if self.ip else "",
			self.label
		)

	def __hash__ (self):
		# esi and label MUST *NOT* be part of the hash
		return hash((self.rd,self.etag,self.mac,self.ip))

	def _pack (self):
		if not self._packed:
			ip = self.ip.pack() if self.ip else ''
			self._packed = "%s%s%s%s%s%s%s%s" % (
				self.rd.pack(),
				self.esi.pack(),
				self.etag.pack(),
				chr(self.maclen),  # only 48 supported by the draft
				self.mac.pack(),
				chr(len(ip)*8 if ip else '\x00'),
				ip,
				self.label.pack()
			)
		return self._packed

	@classmethod
	def unpack (cls, data):
		datalen = len(data)
		rd = RouteDistinguisher.unpack(data[:8])
		esi = ESI.unpack(data[8:18])
		etag = EthernetTag.unpack(data[18:22])
		maclength = ord(data[22])

		if (maclength > 48 or maclength < 0):
			raise Notify(3,5,'invalid MAC Address length in %s' % cls.NAME)
		end = 23 + 6 # MAC length MUST be 6

		mac = MACQUAL.unpack(data[23:end])

		length = ord(data[end])
		iplen = length / 8

		if datalen in [33,36]:  # No IP information (1 or 2 labels)
			iplenUnpack = 0
			if iplen != 0:
				raise Notify(3,5,"IP length is given as %d, but current MAC route has no IP information" % iplen)
		elif datalen in [37, 40]:  # Using IPv4 addresses (1 or 2 labels)
			iplenUnpack = 4
			if (iplen > 32 or iplen < 0):
				raise Notify(3,5,"IP field length is given as %d, but current MAC route is IPv4 and valus is out of range" % iplen)
		elif datalen in [49, 52]:  # Using IPv6 addresses (1 or 2 labels)
			iplenUnpack = 16
			if (iplen > 128 or iplen < 0):
				raise Notify(3,5,"IP field length is given as %d, but current MAC route is IPv6 and valus is out of range" % iplen)
		else:
			raise Notify(3,5,"Data field length is given as %d, but does not match one of the expected lengths" % datalen)

		ip = IP.unpack(data[end+1:end+1+iplenUnpack])
		label = Labels.unpack(data[end+1+iplenUnpack:end+1+iplenUnpack+3])

		return cls(rd,esi,etag,mac,maclength,label,ip,data)
