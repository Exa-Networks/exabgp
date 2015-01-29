"""
mac.py

Created by Thomas Morin on 2014-06-23.
Copyright (c) 2014-2015 Orange. All rights reserved.
"""

from exabgp.protocol.ip import IP
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier.labels import Labels
from exabgp.bgp.message.update.nlri.qualifier.esi import ESI
from exabgp.bgp.message.update.nlri.qualifier.etag import EthernetTag

from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN


# ===================================================================== EVPNNLRI

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

class MAC (EVPN):
	CODE = 2
	NAME = "MAC/IP advertisement"
	SHORT_NAME = "MACAdv"

	def __init__ (self, rd, esi, etag, mac, maclen, label,ip,packed=None):
		EVPN.__init__(self,packed)
		self.rd = rd
		self.esi = esi
		self.etag = etag
		self.maclen = maclen
		self.mac = mac
		self.ip = ip
		self.label = label if label else Labels.NOLABEL
		self.pack()

	def __str__ (self):
		return "%s:%s:%s:%s:%s:%s%s:%s" % (
			self._prefix(),
			self.rd,
			self.esi,
			self.etag,
			self.mac,
			"" if len(self.mac) == 48 else "/%d" % self.maclen,
			self.ip if self.ip else "",
			self.label
		)

	def __cmp__ (self, other):
		if not isinstance(other,self.__class__):
			return -1
		if self.rd != other.rd:
			return -1
		# if self.esi == other.esi:  # MUST NOT be part of the test
		# 	return -1
		# if self.label == other.label:  # MUST NOT be part of the test
		# 	return -1
		if self.etag != other.etag:
			return -1
		if self.mac != other.mac:
			return -1
		if self.ip != other.ip:
			return -1
		return 0

	# XXX: FIXME: improve for better performance?
	def __hash__ (self):
		# esi and label MUST *NOT* be part of the hash
		return hash("%s:%s:%s:%s" % (self.rd,self.etag,self.mac,self.ip))

	def pack (self):
		if not self.packed:
			ip = self.ip.pack() if self.ip else ''
			value = "%s%s%s%s%s%s%s%s" % (
				self.rd.pack(),
				self.esi.pack(),
				self.etag.pack(),
				chr(len(self.maclen)),  # will most likely always be 10
				self.mac.pack(),
				chr(len(ip.pack()) if ip else '\x00'),
				ip,
				self.label.pack()
			)
			self.packed = value
		return self.packed

	@classmethod
	def unpack (cls, data):
		rd = RouteDistinguisher.unpack(data[:8])
		esi = ESI.unpack(data[8:18])
		etag = EthernetTag.unpack(data[18:22])
		maclength = ord(data[22])

		if maclength % 8 != 0:
			raise Exception('invalid MAC Address length in %s' % cls.NAME)
		end = 23 + maclength/8

		mac = MAC.unpack(data[23:end])

		length = ord(data[end])
		if length % 8 != 0:
			raise Exception('invalid IP Address length in %s' % cls.NAME)
		iplen = length / 8

		ip = IP.unpack(data[end+1:end+1+iplen])
		label = Labels.unpack(data[end+1+iplen:])

		return cls(rd,esi,etag,mac,length,label,ip,data)
