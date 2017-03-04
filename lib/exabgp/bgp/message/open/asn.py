# encoding: utf-8
"""
asn.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import pack
from struct import unpack

# =================================================================== ASN


class ASN (long):
	def asn4 (self):
		return self >= pow(2,16)

	def pack (self, negotiated=None):
		asn4 = negotiated if negotiated is not None else self.asn4()
		if asn4:
			return pack('!L',self)
		return pack('!H',self)

	@classmethod
	def unpack (cls, data, klass=None):
		klass = cls if klass is None else klass
		asn4 = True if len(data) == 4 else False
		return klass(unpack('!L' if asn4 else '!H',data)[0])

	def __len__ (self):
		if self.asn4():
			return 4
		return 2

	def extract (self):
		return [pack('!L',self)]

	def trans (self):
		if self.asn4():
			return AS_TRANS
		return self

AS_TRANS = ASN(23456)
