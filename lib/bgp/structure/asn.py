#!/usr/bin/env python
# encoding: utf-8
"""
asn.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2010 Exa Networks. All rights reserved.
"""


from struct import pack

# =================================================================== ASN

class ASN (int):
	# regex = "(?:0[xX][0-9a-fA-F]{1,8}|\d+:\d+|\d+)"
	length = 2

	def four (self):
		self.length = 4
		return self

	def pack (self):
		if self.length == 2:
			return pack('!H',self)
		return pack('!L',self)

	def __len__ (self):
		return self.length

