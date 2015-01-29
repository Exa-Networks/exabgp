# encoding: utf-8
"""
labels.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2014-2015 Orange. All rights reserved.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

# TODO: take into account E-VPN specs that specify the role of the first bit of ESI
# (since draft-ietf-l2vpn-evpn-05)


# Ethernet Segment Identifier
class ESI (object):
	DEFAULT = ''.join(chr(0) for _ in range(0,10))
	MAX = ''.join(chr(0xFF) for _ in range(0,10))

	__slots__ = ['esi']

	def __init__ (self, esi=None):
		self.esi = self.DEFAULT if esi is None else esi

	def __str__ (self):
		if self.esi == self.DEFAULT:
			return "-"
		return ":".join('%02x' % ord(_) for _ in self.esi)

	def __repr__ (self):
		return self.__str__()

	def pack (self):
		return self.esi

	def __len__ (self):
		return 10

	def __cmp__ (self, other):
		if not isinstance(other,self.__class__):
			return -1
		if self.esi != other.esi:
			return -1
		return 0

	def __hash__ (self):
		return hash(self.esi)

	@classmethod
	def unpack (cls, data):
		return cls(data[:10])
