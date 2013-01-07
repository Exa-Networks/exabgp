# encoding: utf-8
"""
asn.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""


from struct import pack

# =================================================================== ASN

class ASN (long):
	def asn4 (self):
		return self > pow(2,16)

	def pack (self,asn4=None):
		if asn4 is None:
			asn4 = self.asn4()
		if asn4:
			return pack('!L',self)
		return pack('!H',self)

	def __len__ (self):
		if self.asn4():
			return 4
		return 2

	def extract (self):
		return [pack('!L',self)]

	def trans (self):
		if self.asn4():
			return AS_TRANS.pack()
		return self.pack()

AS_TRANS = ASN(23456)
