# encoding: utf-8
"""
encapsulation.py

Created by Thomas Mangin on 2014-06-21.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

from struct import pack
from struct import unpack

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity


# ================================================================== TrafficRate
# RFC 5575

@ExtendedCommunity.register
class TrafficRate (ExtendedCommunity):
	COMMUNITY_TYPE = 0x80
	COMMUNITY_SUBTYPE = 0x06

	__slots__ = ['asn','rate']

	def __init__ (self, asn, rate, community=None):
		self.asn = asn
		self.rate = rate
		ExtendedCommunity.__init__(
			self,
			community if community is not None else pack(
				"!2sHf",
				self._subtype(),
				asn,rate
			)
		)

	def __repr__ (self):
		return "rate-limit %d" % self.rate

	@staticmethod
	def unpack (data):
		asn,rate = unpack('!Hf',data[2:8])
		return TrafficRate(ASN(asn),rate,data[:8])


# ================================================================ TrafficAction
# RFC 5575

@ExtendedCommunity.register
class TrafficAction (ExtendedCommunity):
	COMMUNITY_TYPE = 0x80
	COMMUNITY_SUBTYPE = 0x07

	_sample = {
		False: 0x0,
		True:  0x2,
	}

	_terminal = {
		False: 0x0,
		True:  0x1,
	}

	__slots__ = ['sample','terminal']

	def __init__ (self, sample, terminal, community=None):
		self.sample = sample
		self.terminal = terminal
		bitmask = self._sample[sample] | self._terminal[terminal]
		ExtendedCommunity.__init__(
			self,
			community if community is not None else pack(
				'!2sLBB',
				self._subtype(),
				0,0,bitmask
			)
		)

	def __repr__ (self):
		s = []
		if self.sample:
			s.append('sample')
		if self.terminal:
			s.append('terminal')
		return 'action %s' % '-'.join(s)

	@staticmethod
	def unpack (data):
		bit, = unpack('!B',data[7])
		sample = bool(bit & 0x02)
		terminal = bool(bit & 0x01)
		return TrafficAction(sample,terminal,data[:8])


# ============================================================== TrafficRedirect
# RFC 5575

@ExtendedCommunity.register
class TrafficRedirect (ExtendedCommunity):
	COMMUNITY_TYPE = 0x80
	COMMUNITY_SUBTYPE = 0x08

	__slots__ = ['asn','target']

	def __init__ (self, asn, target, community=None):
		self.asn = asn
		self.target = target
		ExtendedCommunity.__init__(
			self,
			community if community is not None else pack(
				"!2sHL",
				self._subtype(),
				asn,target
			)
		)

	def __repr__ (self):
		return "redirect:%s:%s" % (self.asn,self.target)

	@staticmethod
	def unpack (data):
		asn,target = unpack('!HL',data[2:8])
		return TrafficRedirect(ASN(asn),target,data[:8])


# ================================================================== TrafficMark
# RFC 5575

@ExtendedCommunity.register
class TrafficMark (ExtendedCommunity):
	COMMUNITY_TYPE = 0x80
	COMMUNITY_SUBTYPE = 0x09

	__slots__ = ['dscp']

	def __init__ (self, dscp, community=None):
		self.dscp = dscp
		ExtendedCommunity.__init__(
			self,
			community if community is not None else pack(
				"!2sLBB",
				self._subtype(),
				0,0,dscp
			)
		)

	def __repr__ (self):
		return "mark %d" % self.dscp

	@staticmethod
	def unpack (data):
		dscp, = unpack('!B',data[7])
		return TrafficMark(dscp,data[:8])


# =============================================================== TrafficNextHop
# draft-simpson-idr-flowspec-redirect-02

# XXX: FIXME: I guess this should be a subclass of NextHop or IP ..

@ExtendedCommunity.register
class TrafficNextHop (ExtendedCommunity):
	COMMUNITY_TYPE = 0x08
	COMMUNITY_SUBTYPE = 0x00

	__slots__ = ['copy']

	def __init__ (self, copy, community=None):
		self.copy = copy
		ExtendedCommunity.__init__(
			self,
			community if community is not None else pack(
				"!2sLH",
				self._subtype(),
				0,1 if copy else 0
			)
		)

	def __repr__ (self):
		return "copy-to-nexthop" if self.copy else "redirect-to-nexthop"

	@staticmethod
	def unpack (data):
		bit, = unpack('!B',data[7])
		return TrafficNextHop(bool(bit & 0x01),data[:8])


# ============================================================ TrafficRedirectIP
# RFC 5575
# If we need to provide the <IP>:<ASN> form for the FlowSpec Redirect ...

# import socket
# Do not use socket, use IPv4.ntop or pton

# TrafficRedirectASN = TrafficRedirect

# class TrafficRedirectIP (ExtendedCommunity):
# 	COMMUNITY_TYPE = 0x80
# 	COMMUNITY_SUBTYPE = 0x08

# 	def __init__ (self, ip, target, community=None):
# 		self.ip = ip
# 		self.target = target
# 		ExtendedCommunity.__init__(self,community if community is not None else pack("!BB4sH",0x80,0x08,socket.inet_pton(socket.AF_INET,ip),target))

# 	def __str__ (self):
# 		return "redirect %s:%d" % (self.ip,self.target)

# 	@staticmethod
# 	def unpack (data):
# 		ip,target = unpack('!4sH',data[2:8])
# 		return TrafficRedirectIP(socket.inet_ntop(socket.AF_INET,ip),target,data[:8])
