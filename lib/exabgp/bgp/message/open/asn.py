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
	cache = {}

	@classmethod
	def _cache (cls,value,klass):
		if value in cls.cache:
			return cls.cache[value]
		instance = klass(value)
		cls.cache[value] = instance
		return instance

	def asn4 (self):
		return self > pow(2,16)

	def pack (self, negotiated=None):
		asn4 = negotiated if negotiated is not None else self.asn4()
		return pack('!L' if asn4 else '!H',self)

	@classmethod
	def unpack (cls, data, klass=None):
		value = unpack('!L' if len(data) == 4 else '!H',data)[0]
		return cls._cache(value,cls if klass is None else klass)

	def __len__ (self):
		return 4 if self.asn4() else 2

	def extract (self):
		return [pack('!L',self)]

	def trans (self):
		if self.asn4():
			return AS_TRANS.pack()
		return self.pack()

	@classmethod
	def from_string (cls, value):
		return cls._cache(long(value),cls)

AS_TRANS = ASN(23456)
