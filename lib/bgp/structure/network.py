#!/usr/bin/env python
# encoding: utf-8
"""
network.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import socket
from struct import *

# =================================================================== IP

class IP (object):
	def __init__ (self,value):
		v4 = False
		try:
			pack = socket.inet_pton(socket.AF_INET, str(value))
			numeric = unpack('>L',pack)[0]
			string = str(value)
			v4 = True
		except socket.error:
			pass
		except TypeError:
			pass

		if not v4:
			try:
				pack = socket.inet_pton(socket.AF_INET6, str(value))
				a,b,c,d = unpack('>LLLL',pack)
				numeric = (a << 96) + (b << 64) + (c << 32) + d
				string = str(value).lower()
			except socket.error:
				raise ValueError('"%s" is an invalid address' % str(value))
			except TypeError:
				raise ValueError('"%s" is an invalid address' % str(value))

		self.numeric = numeric
		self._pack = pack
		self.string = string

		if v4:
			self.version = 4
			self.length = 32
		else:
			self.version = 6
			self.length = 128

	def pack (self):
		return self._pack

	def __str__ (self):
		return self.string

	def __len__ (self):
		return self.version
		
	def __eq__ (self,other):
		return self.numeric == other.numeric and self.version == other.version
		
	# XXX: Should we implement the other test to not create bad surprised ? ...

# =================================================================== Mask

# Super sub-optimal as code... make length as parameter of __init__ ?
class Mask (int):
	def new (self,mask,length):
		#slash_to_size = dict([(length-bits,(1<<bits)) for bits in range(0,length+1)])
		#slash_to_mask = dict([(length-bits,(1L<<length) - (1<<bits)) for bits in range(0,length+1)])
		mask_to_slash = dict([((1L<<length) - (1<<bits),length-bits) for bits in range(0,length+1)])
		ipv4_to_slash = dict([("%d.%d.%d.%d" % (k>>24, k>>16 & 0xFF ,k>>8 & 0xFF, k&0xFF),mask_to_slash[k]) for k in mask_to_slash.keys()])

		#regex_mask = '(?:\d|[12]\d|3[012])'
		try:
			slash = int(mask)
		except ValueError:
			try:
				slash = ipv4_to_slash[mask]
			except KeyError:
				raise ValueError('the netmask is invalid %s' % str(mask))

		if not slash in range(0,length+1):
			return ValueError('the netmask is invalid /%s' % str(slash))

		return Mask(slash)

	def pack (self):
		return chr(self)

	def __len__ (self):
		return 1

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

