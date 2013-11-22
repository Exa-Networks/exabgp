# encoding: utf-8
"""
community.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from struct import pack,unpack

from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute import Flag,Attribute

# =================================================================== Community

class Community (object):
	NO_EXPORT           = pack('!L',0xFFFFFF01)
	NO_ADVERTISE        = pack('!L',0xFFFFFF02)
	NO_EXPORT_SUBCONFED = pack('!L',0xFFFFFF03)
	NO_PEER             = pack('!L',0xFFFFFF04)

	cache = {}
	caching = False

	def __init__ (self,community):
		self.community = community
		if community == self.NO_EXPORT:
			self._str = 'no-export'
		elif community == self.NO_ADVERTISE:
			self._str = 'no-advertise'
		elif community == self.NO_EXPORT_SUBCONFED:
			self._str = 'no-export-subconfed'
		else:
			self._str = "%d:%d" % unpack('!HH',self.community)

	def json (self):
		return "[ %d, %d ]" % unpack('!HH',self.community)

	def pack (self,asn4=None):
		return self.community

	def __str__ (self):
		return self._str

	def __len__ (self):
		return 4

	def __eq__ (self,other):
		return self.community == other.community

	def __ne__ (self,other):
		return self.community != other.community

def cachedCommunity (community):
	if community in Community.cache:
		return Community.cache[community]
	instance = Community(community)
	if Community.caching:
		Community.cache[community] = instance
	return instance

# Always cache well-known communities, they will be used a lot
if not Community.cache:
	Community.cache[Community.NO_EXPORT] = Community(Community.NO_EXPORT)
	Community.cache[Community.NO_ADVERTISE] = Community(Community.NO_ADVERTISE)
	Community.cache[Community.NO_EXPORT_SUBCONFED] = Community(Community.NO_EXPORT_SUBCONFED)
	Community.cache[Community.NO_PEER] = Community(Community.NO_PEER)


# =================================================================== Communities (8)

class Communities (Attribute):
	ID = AttributeID.COMMUNITY
	FLAG = Flag.TRANSITIVE|Flag.OPTIONAL
	MULTIPLE = False

	def __init__ (self,communities=None):
		# Must be None as = param is only evaluated once
		if communities:
			self.communities = communities
		else:
			self.communities = []

	def add(self,data):
		return self.communities.append(data)

	def pack (self,asn4=None):
		if len(self.communities):
			return self._attribute(''.join([c.pack() for c in self.communities]))
		return ''

	def __str__ (self):
		l = len(self.communities)
		if l > 1:
			return "[ %s ]" % " ".join(str(community) for community in self.communities)
		if l == 1:
			return str(self.communities[0])
		return ""

	def json (self):
		return "[ %s ]" % ", ".join(community.json() for community in self.communities)

# =================================================================== ECommunity

# http://www.iana.org/assignments/bgp-extended-communities

# MUST ONLY raise ValueError
def to_ExtendedCommunity (data):
	nb_separators = data.count(':')
	if nb_separators == 2:
		command,ga,la = data.split(':')
	elif nb_separators == 1:
		command = 'target'
		ga,la = data.split(':')
	else:
		raise ValueError('invalid extended community %s (only origin or target are supported) ' % command)


	header = chr(0x00)
	if command == 'origin':
		subtype = chr(0x03)
	elif command == 'target':
		subtype = chr(0x02)
	else:
		raise ValueError('invalid extended community %s (only origin or target are supported) ' % command)

	if '.' in ga or '.' in la:
		gc = ga.count('.')
		lc = la.count('.')
		if gc == 0 and lc == 3:
			# ASN first, IP second
			global_admin = pack('!H',int(ga))
			local_admin = pack('!BBBB',*[int(_) for _ in la.split('.')])
		elif gc == 3 and lc == 0:
			# IP first, ASN second
			global_admin = pack('!BBBB',*[int(_) for _ in ga.split('.')])
			local_admin = pack('!H',int(la))
		else:
			raise ValueError('invalid extended community %s ' % data)
	else:
		if command == 'target':
			global_admin = pack('!H',int(ga))
			local_admin = pack('!I',int(la))
		elif command == 'origin':
			global_admin = pack('!I',int(ga))
			local_admin = pack('!H',int(la))
		else:
			raise ValueError('invalid extended community %s (only origin or target are supported) ' % command)

	return ECommunity(header+subtype+global_admin+local_admin)

class ECommunity (object):
	ID = AttributeID.EXTENDED_COMMUNITY
	FLAG = Flag.TRANSITIVE|Flag.OPTIONAL
	MULTIPLE = False

	# size of value for data (boolean: is extended)
	length_value = {False:7, True:6}
	name = {False: 'regular', True: 'extended'}

	def __init__ (self,community):
		# Two top bits are iana and transitive bits
		self.community = community

	def iana (self):
		return not not (self.community[0] & 0x80)

	def transitive (self):
		return not not (self.community[0] & 0x40)

	def pack (self,asn4=None):
		return self.community

	def json (self):
		return '[ %s, %s, %s, %s, %s, %s, %s, %s ]' % unpack('!BBBBBBBB',self.community)

	def __str__ (self):
		# 30/02/12 Quagga communities for soo and rt are not transitive when 4360 says they must be, hence the & 0x0F
		community_type = ord(self.community[0]) & 0x0F
		community_stype = ord(self.community[1])
		# Target
		if community_stype == 0x02:
			if community_type in (0x00,0x02):
				asn = unpack('!H',self.community[2:4])[0]
				ip = ip = '%s.%s.%s.%s' % unpack('!BBBB',self.community[4:])
				return "target:%d:%s" % (asn,ip)
			if community_type == 0x01:
				ip = '%s.%s.%s.%s' % unpack('!BBBB',self.community[2:6])
				asn = unpack('!H',self.community[6:])[0]
				return "target:%s:%d" % (ip,asn)
		# Origin
		if community_stype == 0x03:
			if community_type in (0x00,0x02):
				asn = unpack('!H',self.community[2:4])[0]
				ip = unpack('!L',self.community[4:])[0]
				return "origin:%d:%s" % (asn,ip)
			if community_type == 0x01:
				ip = '%s.%s.%s.%s' % unpack('!BBBB',self.community[2:6])
				asn = unpack('!H',self.community[6:])[0]
				return "origin:%s:%d" % (ip,asn)

		# Traffic rate
		if self.community.startswith('\x80\x06'):
			speed = unpack('!f',self.community[4:])[0]
			if speed == 0.0:
				return 'discard'
			return 'rate-limit %d' % speed
		# redirect
		elif self.community.startswith('\x80\x07'):
			actions = []
			value = ord(self.community[-1])
			if value & 0x2:
				actions.append('sample')
			if value & 0x1:
				actions.append('terminal')
			return 'action %s' % '-'.join(actions)
		elif self.community.startswith('\x80\x08'):
			return 'redirect %d:%d' % (unpack('!H',self.community[2:4])[0],unpack('!L',self.community[4:])[0])
		elif self.community.startswith('\x80\x09'):
			return 'mark %d' % ord(self.community[-1])
		elif self.community.startswith('\x80\x00'):
			if self.community[-1] == '\x00':
				return 'redirect-to-nexthop'
			return 'copy-to-nexthop'
		else:
			h = 0x00
			for byte in self.community:
				h <<= 8
				h += ord(byte)
			return "0x%016X" % h

	def __len__ (self):
		return 8

	def __cmp__ (self,other):
		return cmp(self.pack(),other.pack())

# =================================================================== ECommunities (16)

#def new_ECommunities (data):
#	communities = ECommunities()
#	while data:
#		ECommunity = unpack(data[:8])
#		data = data[8:]
#		communities.add(ECommunity(ECommunity))
#	return communities

class ECommunities (Communities):
	ID = AttributeID.EXTENDED_COMMUNITY

# =================================================================== FlowSpec Defined Extended Communities

def _to_FlowCommunity (action,data):
	return ECommunity(pack('!H',action) + data[:6])

# rate is bytes/seconds
def to_FlowTrafficRate (asn,rate):
	return _to_FlowCommunity (0x8006,pack('!H',asn) + pack('!f',rate))

def to_FlowTrafficAction (sample,terminal):
	number = 0
	if terminal: number += 0x1
	if sample: number += 0x2
	return _to_FlowCommunity (0x8007,'\x00\x00\x00\x00\x00' + chr(number))

def to_FlowRedirect (copy):
	payload = '\x00\x00\x00\x00\x00\x01' if copy else '\x00\x00\x00\x00\x00\x00'
	return _to_FlowCommunity (0x8000,payload)

def to_FlowRedirectVRFASN (asn,number):
	return _to_FlowCommunity (0x8008,pack('!H',asn) + pack('!L',number))

def to_FlowRedirectVRFIP (ip,number):
	return _to_FlowCommunity (0x8008,pack('!L',ip) + pack('!H',number))

def to_FlowTrafficMark (dscp):
	return _to_FlowCommunity (0x8009,'\x00\x00\x00\x00\x00' + chr(dscp))

def to_RouteOriginCommunity (asn,number,hightype=0x01):
	return ECommunity(chr(hightype) + chr(0x03) + pack('!H',asn) + pack('!L',number))

# VRF is ASN:Long
def to_RouteTargetCommunity_00 (asn,number):
	return ECommunity(chr(0x00) + chr(0x02) + pack('!H',asn) + pack('!L',number))

# VRF is A.B.C.D:Short
def to_RouteTargetCommunity_01 (ipn,number):
	return ECommunity(chr(0x01) + chr(0x02) + pack('!L',ipn) + pack('!H',number))

#def to_ASCommunity (subtype,asn,data,transitive):
#	r = chr(0x00)
#	if transitive: r += chr(0x40)
#	return ECommunity(r + chr(subtype) + pack('!H',asn) + ''.join([chr(c) for c in data[:4]]))
#
#import socket
#def toIPv4Community (subtype,data,transitive):
#	r = chr(0x01)
#	if transitive: r += chr(0x40)
#	return ECommunity(r + chr(subtype) + socket.inet_pton(socket.AF_INET,ipv4) + ''.join([chr(c) for c in data[:2]]))
#
#def to_OpaqueCommunity (subtype,data,transitive):
#	r = chr(0x03)
#	if transitive: r += chr(0x40)
#	return ECommunity(r + chr(subtype) + ''.join([chr(c) for c in data[:6]]))

# See RFC4360
# 0x00, 0x02 Number is administrated by a global authority
# Format is asn:route_target (2 bytes:4 bytes)
# 0x01, Number is administered by the ASN owner
# Format is ip:route_target  (4 bytes:2 bytes)
# 0x02 and 0x03 .. read the RFC :)
