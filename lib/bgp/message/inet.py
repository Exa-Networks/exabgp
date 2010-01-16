#!/usr/bin/env python
# encoding: utf-8
"""
network.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import socket
import math
from bgp.structure.afi import AFI
from bgp.structure.safi import SAFI

# =================================================================== IP

def to_IPv4 (ip):
	pack = socket.inet_pton(socket.AF_INET,ip)
	return IP(pack,AFI.ipv4,SAFI.unicast,ip)

def to_IPv6 (ip):
	pack = socket.inet_pton(socket.AF_INET6,ip)
	return IP(pack,AFI.ipv6,SAFI.unicast,ip)

def to_IP (value):
	if value.count(':'):
		return to_IPv6(value)
	return to_IPv4(value)

class IP (object):
	_af = {
		AFI.ipv4: socket.AF_INET,
		AFI.ipv6: socket.AF_INET6,
	}

	def __init__ (self,pip,afi,safi,ip=None):
		# XXX: Add a check to make sure it is Unicast(/Multicast?) 
		self.afi = AFI(afi)
		self.safi = SAFI(safi)
		self.pip = pip
		self._ip = ip

	def ip (self):
		if not self._ip:
			if self.afi == AFI.ipv4:
				self._ip = socket.inet_ntop(self._af[self.afi],self.pip)
			else:
				self._ip = socket.inet_ntop(self._af[self.afi],self.pip)
		return self._ip

	def pack (self):
		return self.pip

	def packed (self):
		if self.afi == AFI.ipv4:
			return self.pip[1:] + '\0'*(5-len(self.pip))
		return self.pip[1:] + '\0'*(17-len(self.pip))

	def __str__ (self):
		return "%s" % self.ip()

	def __len__ (self):
		return len(self.pip)

	def __eq__ (self,other):
		if type(self) == type(other):
			return self.pip == other.pip and self.afi == other.afi and self.safi == other.safi
		# XXX: Should we implement the other test to not create bad surprised ? ...
		if type(other) != type(None):
			import warnings
			warnings.warn('we should never compare things which are not comparable %s and %s' % (type(self),type(other)))
		return False


# =================================================================== NLRI

def new_NLRI (data,afi=AFI.ipv4,safi=SAFI.unicast):
	size = int(math.ceil(float(ord(data[0]))/8)) + 1
	return NLRI(data[:size],afi,safi)

def to_NLRI(ip,netmask):
	try:
		nm = chr(int(netmask))
	except ValueError:
		raise ValueError('Invalid Netmask %s' % str(netmask))
	try:
		pack = socket.inet_pton(socket.AF_INET,ip)
		afi = AFI.ipv4
	except socket.error:
		try:
			pack = socket.inet_pton(socket.AF_INET6,ip)
			afi = AFI.ipv6
		except socket.error:
			raise ValueError('Invalid IP %s' % ip)
	size = int(math.ceil(float(netmask)/8))
	return NLRI("%s%s" % (nm,pack[:size]),afi,SAFI.unicast)

class NLRI (IP):
	_af = {
		AFI.ipv4: socket.AF_INET,
		AFI.ipv6: socket.AF_INET6,
	}

	def __init__ (self,raw,afi,safi):
		self.afi = AFI(afi)
		self.safi = SAFI(safi)
		self.raw = raw
		self._ip = None
		self._mask = None

	def ip (self):
		if self.afi == AFI.ipv4: l = 5
		else: l = 17
		return IP(self.raw[1:] + '\0'*(l-len(self.raw)),self.api,self.safi)

	def mask (self):
		return ord(self.raw[0])

	def pack (self):
		return self.raw

	def __cmp__ (self,other):
		return \
			self.afi == other.afi and \
			self.safi == other.safi and \
			self.raw == other.raw

	def __str__ (self):
		if not self._ip:
			if self.afi == AFI.ipv4:
				self._ip = socket.inet_ntop(self._af[self.afi],self.raw[1:] + '\0'*(5-len(self.raw)))
				self._mask = ord(self.raw[0])
			if self.afi == AFI.ipv6:
				self._ip = socket.inet_ntop(self._af[self.afi],self.raw[1:] + '\0'*(17-len(self.raw)))
				self._mask = ord(self.raw[0])

		if self.afi in [AFI.ipv4,AFI.ipv6]:
			return "NLRI %s/%s %s/%d" % (str(self.afi),str(self.safi), self._ip,self._mask)
		else:
			return "NLRI %s/%s [%s]" % (hex(self.afi),hex(self.safi),''.join([hex(ord(_)) for _ in self.raw]))

	def __len__ (self):
		return len(self.raw)

	def __eq__ (self,other):
		if type(self) == type(other):
			return self.raw == other.raw and self.afi == other.afi
		# XXX: Should we implement the other test to not create bad surprised ? ...
		if type(other) != type(None):
			import warnings
			warnings.warn('we should never compare things which are not comparable %s and %s' % (type(self),type(other)))
		return False

#		return int(math.ceil(float(self.mask)/8)) + 1

