# encoding: utf-8
"""
etag.py

Created by Thomas Mangin on 2014-06-26.
Copyright (c) 2014-2015 Orange. All rights reserved.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

# TODO: take into account E-VPN specs that specify the role of the first bit of ESI
# (since draft-ietf-l2vpn-evpn-05)

from struct import pack
from struct import unpack


class EthernetTag (object):
	MAX = pow(2,32)-1

	__slots__ = ['tag']

	def __init__ (self, tag=0):
		self.tag = tag

	def __str__ (self):
		return repr(self.tag)

	def __repr__ (self):
		return repr(self.tag)

	def pack (self):
		return pack("!L",self.tag)

	def __len__ (self):
		return 4

	def __cmp__ (self, other):
		if not isinstance(other,self.__class__):
			return -1
		if self.tag != other.tag:
			return -1
		return 0

	def __hash__ (self):
		return hash(self.tag)

	@classmethod
	def unpack (cls, data):
		return cls(unpack("!L",data[:4])[0])
