# encoding: utf-8
"""
ip/__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""

import socket

from exabgp.protocol.family import AFI, SAFI


# =========================================================================== IP
#

class IP (object):
	_known = dict()

	_UNICAST = SAFI(SAFI.unicast)
	_MULTICAST = SAFI(SAFI.multicast)

	_multicast_range = set(range(224,240))  # 239

	def __init__ (self):
		raise Exception("You should use IP.create() to use IP")

	def init (self,ip,packed):
		self.ip = ip
		self.packed = packed

	@staticmethod
	def pton (ip):
		return socket.inet_pton(IP.toaf(ip),ip)

	@staticmethod
	def ntop (data):
		return socket.inet_ntop(socket.AF_INET if len(data) == 4 else socket.AF_INET6,data)

	@staticmethod
	def toaf (ip):
		# the orders matters as ::FFFF:<ipv4> is an IPv6 address
		if ':' in ip:
			return socket.AF_INET6
		if '.' in ip:
			return socket.AF_INET
		raise Exception('unrecognised ip address %s' % ip)

	@staticmethod
	def toafi (ip):
		# the orders matters as ::FFFF:<ipv4> is an IPv6 address
		if ':' in ip:
			return AFI.ipv6
		if '.' in ip:
			return AFI.ipv4
		raise Exception('unrecognised ip address %s' % ip)

	@staticmethod
	def tosafi (ip):
		if ':' in ip:
			# XXX: FIXME: I assume that ::FFFF:<ip> must be treated unicast
			# if int(ip.split(':')[-1].split('.')[0]) in IP._multicast_range:
			return SAFI.unicast
		elif '.' in ip:
			if int(ip.split('.')[0]) in IP._multicast_range:
				return SAFI.multicast
			return SAFI.unicast
		raise Exception('unrecognised ip address %s' % ip)

	@staticmethod
	def length (afi):
		return 4 if afi == AFI.ipv4 else 16

	def pack (self):
		return self.packed

	def __str__ (self):
		return self.ip

	def __repr__ (self):
		return str(self)

	def __cmp__ (self,other):
		if not isinstance(other, self.__class__):
			return -1
		if self.packed == other.packed:
			return 0
		if self.packed < other.packed:
			return -1
		return 1

	@classmethod
	def klass (cls,ip):
		# the orders matters as ::FFFF:<ipv4> is an IPv6 address
		if ':' in ip:
			afi = IPv6.afi
		elif '.' in ip:
			afi = IPv4.afi
		else:
			raise Exception('can not decode this ip address : %s' % ip)
		if afi in cls._known:
			return cls._known[afi]

	@classmethod
	def create (cls,ip,data=None):
		return cls.klass(ip)(ip,data)

	@classmethod
	def register (cls):
		cls._known[cls.afi] = cls

	@classmethod
	def unpack (cls,data):
		return cls.create(IP.ntop(data),data)


# ========================================================================= IPv4
#

class IPv4 (IP):
	# lower case to match the class Address API
	afi = AFI.ipv4

	def __init__ (self,ip,packed=None):
		self.init(ip,packed if packed else socket.inet_pton(socket.AF_INET,ip))

	def __len__ (self):
		return 4

	def unicast (self):
		return not self.multicast()

	def multicast (self):
		return ord(self.packed[0]) in set(range(224,240))  # 239 is last

	def ipv4 (self):
		return True

	def ipv6 (self):
		return False

	# klass is a trick for NextHop
	@classmethod
	def unpack (cls,data,klass=None):
		ip = socket.inet_ntop(socket.AF_INET,data)
		if klass:
			return klass(ip,data)
		return cls(ip,data)

IPv4.register()


# ========================================================================= IPv6
#

class IPv6 (IP):
	# lower case to match the class Address API
	afi = AFI.ipv6

	def __init__ (self,ip,packed=None):
		self.init(ip,packed if packed else socket.inet_pton(socket.AF_INET6,ip))

	def __len__ (self):
		return 16

	def ipv4 (self):
		return False

	def ipv6 (self):
		return True

	def unicast (self):
		return True

	def multicast (self):
		return False

	@classmethod
	def unpack (cls,data):
		return cls(socket.inet_ntop(socket.AF_INET6,data))

IPv6.register()
