# encoding: utf-8
"""
bgp.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import unpack


# =========================================================== RouteDistinguisher
# RFC 4364

class RouteDistinguisher (object):

	__slots__ = ['rd','_len']

	def __init__ (self, rd):
		self.rd = rd
		self._len = len(self.rd)

	def pack (self):
		return self.rd

	def __len__ (self):
		return self._len

	def _str (self):
		t,c1,c2,c3 = unpack('!HHHH',self.rd)
		if t == 0:
			rd = '%d:%d' % (c1,(c2 << 16)+c3)
		elif t == 1:
			rd = '%d.%d.%d.%d:%d' % (c1 >> 8,c1 & 0xFF,c2 >> 8,c2 & 0xFF,c3)
		elif t == 2:
			rd = '%d:%d' % ((c1 << 16) + c2,c3)
		else:
			rd = str(self.rd)
		return rd

	def json (self):
		if not self.rd:
			return ''
		return '"route-distinguisher": "%s"' % self._str()

	def __str__ (self):
		if not self.rd:
			return ''
		return ' route-distinguisher %s' % self._str()

	@classmethod
	def unpack (cls, data):
		return cls(data[:8])

RouteDistinguisher.NORD = RouteDistinguisher('')
