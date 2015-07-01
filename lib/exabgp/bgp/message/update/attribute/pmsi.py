# encoding: utf-8
"""
pmsi_tunnel.py

Created by Thomas Morin on 2014-06-10.
Copyright (c) 2014-2015 Orange. All rights reserved.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

from struct import pack
from struct import unpack

from exabgp.protocol.ip import IPv4
from exabgp.bgp.message.update.attribute.attribute import Attribute

# http://tools.ietf.org/html/rfc6514#section-5
#
#  +---------------------------------+
#  |  Flags (1 octet)                |
#  +---------------------------------+
#  |  Tunnel Type (1 octets)         |
#  +---------------------------------+
#  |  MPLS Label (3 octets)          |
#  +---------------------------------+
#  |  Tunnel Identifier (variable)   |
#  +---------------------------------+


# ========================================================================= PMSI
# RFC 6514

@Attribute.register()
class PMSI (Attribute):
	ID = Attribute.CODE.PMSI_TUNNEL
	FLAG = Attribute.Flag.OPTIONAL | Attribute.Flag.TRANSITIVE
	CACHING = True
	TUNNEL_TYPE = -1

	# TUNNEL_TYPE MUST NOT BE DEFINED HERE ( it allows to set it up as a self. value)

	_pmsi_known = dict()
	_name = {
		0: 'No tunnel',
		1: 'RSVP-TE P2MP LSP',
		2: 'mLDP P2MP LSP',
		3: 'PIM-SSM Tree',
		4: 'PIM-SM Tree',
		5: 'BIDIR-PIM Tree',
		6: 'Ingress Replication',
		7: 'mLDP MP2MP LSP',
	}

	__slots__ = ['label','flags','tunnel']

	def __init__ (self, tunnel, label, flags):
		self.label = label    # integer
		self.flags = flags    # integer
		self.tunnel = tunnel  # tunnel id, packed data

	def __eq__ (self, other):
		return \
			self.ID == other.ID and \
			self.FLAG == other.FLAG and \
			self.label == other.label and \
			self.flags == other.flags and \
			self.tunnel == other.tunnel

	def __ne__ (self, other):
		return not self.__eq__(other)

	@staticmethod
	def name (tunnel_type):
		return PMSI._name.get(tunnel_type,'unknown')

	def pack (self, negotiated):
		return self._attribute(
			pack(
				'!BB3s',
				self.flags,
				self.TUNNEL_TYPE,
				pack('!L',self.label << 4)[1:4]
			) + self.tunnel
		)

	# XXX: FIXME: Orange code had 4 (and another reference to it in the code elsewhere)
	def __len__ (self):
		return len(self.tunnel) + 5  # label:1, tunnel type: 1, MPLS label:3

	def prettytunnel (self):
		return "0x" + ''.join('%02X' % ord(_) for _ in self.tunnel) if self.tunnel else ''

	def __repr__ (self):
		return "pmsi:%s:%s:%s:%s" % (
			self.name(self.TUNNEL_TYPE).replace(' ','').lower(),
			str(self.flags) if self.flags else '-',  # why not use zero (0) ?
			str(self.label) if self.label else '-',  # what noy use zero (0) ?
			self.prettytunnel()
		)

	@classmethod
	def register (cls,klass):
		if klass.TUNNEL_TYPE in cls._pmsi_known:
			raise RuntimeError('only one registration for PMSI')
		cls._pmsi_known[klass.TUNNEL_TYPE] = klass
		return klass

	@staticmethod
	def pmsi_unknown (subtype, tunnel, label, flags):
		pmsi = PMSI(tunnel,label,flags)
		pmsi.TUNNEL_TYPE = subtype
		return pmsi

	@classmethod
	def unpack (cls, data, negotiated):
		flags,subtype = unpack('!BB',data[:2])
		label = unpack('!L','\0'+data[2:5])[0] >> 4
		# should we check for bottom of stack before the shift ?
		if subtype in cls._pmsi_known:
			return cls._pmsi_known[subtype].unpack(data[5:],label,flags)
		return cls.pmsi_unknown(subtype,data[5:],label,flags)


# ================================================================= PMSINoTunnel
# RFC 6514

@PMSI.register
class PMSINoTunnel (PMSI):
	TUNNEL_TYPE = 0

	def __init__ (self, label=0,flags=0):
		PMSI.__init__(self,'',label,flags)

	def prettytunnel (self):
		return ''

	@classmethod
	def unpack (cls, tunnel, label, flags):
		return cls(label,flags)


# ======================================================= PMSIIngressReplication
# RFC 6514

@PMSI.register
class PMSIIngressReplication (PMSI):
	TUNNEL_TYPE = 6

	def __init__ (self, ip, label=0,flags=0,tunnel=None):
		self.ip = ip  # looks like a bad name
		PMSI.__init__(self,tunnel if tunnel else IPv4.pton(ip),label,flags)

	def prettytunnel (self):
		return self.ip

	@classmethod
	def unpack (cls, tunnel, label, flags):
		ip = IPv4.ntop(tunnel)
		return cls(ip,label,flags,tunnel)
