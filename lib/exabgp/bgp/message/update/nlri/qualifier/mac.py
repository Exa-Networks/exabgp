# encoding: utf-8
"""
mac.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2014-2015 Orange. All rights reserved.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""


# ========================================================================== MAC
#

class MAC(object):

	__slots__ = ['mac','packed']

	def __init__ (self, mac=None,packed=None):
		self.mac = mac
		self.packed = packed if packed else ''.join(chr(int(_,16)) for _ in mac.split(":"))

	def __str__ (self):
		return ':'.join('%02X' % ord(_) for _ in self.packed)

	def __repr__ (self):
		return self.__str__()

	def pack (self):
		return self.packed

	# Orange code was returning 10 !
	def __len__ (self):
		return 6

	def __cmp__ (self, other):
		if not isinstance(other,self.__class__):
			return -1
		if self.packed != other.packed:
			return -1
		return 0

	# XXX: FIXME: improve for better performance ?
	def __hash__ (self):
		return hash(str(self))

	@classmethod
	def unpack (cls, data):
		return cls(':'.join('%02X' % ord(_) for _ in data[:6]),data[:6])
