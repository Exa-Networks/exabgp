# encoding: utf-8
"""
community.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from struct import pack

from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute import Flag,Attribute

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


class ExtendedCommunities (Communities):
	ID = AttributeID.EXTENDED_COMMUNITY


# ==============================================================================

# http://www.iana.org/assignments/bgp-extended-communities

_known_community = {
	# header and subheader
	'target' : chr(0x00)+chr(0x02),
	'origin' : chr(0x00)+chr(0x03),
	'l2info' : chr(0x80)+chr(0x0A),
}

_size_community = {
	'target' : 2,
	'origin' : 2,
	'l2info' : 4,
}


# MUST ONLY raise ValueError
def to_ExtendedCommunity (data):
	components = data.split(':')
	command = 'target' if len(components) == 2 else components.pop(0)

	if command not in _known_community:
		raise ValueError('invalid extended community %s (only origin,target or l2info are supported) ' % command)

	if len(components) != _size_community[command]:
		raise ValueError('invalid extended community %s, expecting %d fields ' % (command,len(components)))

	header = _known_community[command]

	if command == 'l2info':
		# encaps, control, mtu, site
		return ExtendedCommunity(header+pack('!BBHH',*[int(_) for _ in components]))

	if command in ('target','origin'):
		# global admin, local admin
		ga,la = components

		if '.' in ga or '.' in la:
			gc = ga.count('.')
			lc = la.count('.')
			if gc == 0 and lc == 3:
				# ASN first, IP second
				return ExtendedCommunity(header+pack('!HBBBB',int(ga),*[int(_) for _ in la.split('.')]))
			if gc == 3 and lc == 0:
				# IP first, ASN second
				return ExtendedCommunity(header+pack('!BBBBH',*[int(_) for _ in ga.split('.')]+[int(la)]))
		else:
			if command == 'target':
				return ExtendedCommunity(header+pack('!HI',int(ga),int(la)))
			if command == 'origin':
				return ExtendedCommunity(header+pack('!IH',int(ga),int(la)))

	raise ValueError('invalid extended community %s' % command)


# ===================================================== ExtendedCommunities (16)

#def new_ExtendedCommunities (data):
#	communities = ExtendedCommunities()
#	while data:
#		community = unpack(data[:8])
#		data = data[8:]
#		communities.add(ExtendedCommunity(community))
#	return communities


# =================================================================== FlowSpec Defined Extended Communities

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

def _to_FlowCommunity (action,data):
	return ExtendedCommunity(pack('!H',action) + data[:6])

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
	return ExtendedCommunity(chr(hightype) + chr(0x03) + pack('!H',asn) + pack('!L',number))

# VRF is ASN:Long
def to_RouteTargetCommunity_00 (asn,number):
	return ExtendedCommunity(chr(0x00) + chr(0x02) + pack('!H',asn) + pack('!L',number))

# VRF is A.B.C.D:Short
def to_RouteTargetCommunity_01 (ipn,number):
	return ExtendedCommunity(chr(0x01) + chr(0x02) + pack('!L',ipn) + pack('!H',number))

#def to_ASCommunity (subtype,asn,data,transitive):
#	r = chr(0x00)
#	if transitive: r += chr(0x40)
#	return ExtendedCommunity(r + chr(subtype) + pack('!H',asn) + ''.join([chr(c) for c in data[:4]]))
#
#import socket
#def toIPv4Community (subtype,data,transitive):
#	r = chr(0x01)
#	if transitive: r += chr(0x40)
#	return ExtendedCommunity(r + chr(subtype) + socket.inet_pton(socket.AF_INET,ipv4) + ''.join([chr(c) for c in data[:2]]))
#
#def to_OpaqueCommunity (subtype,data,transitive):
#	r = chr(0x03)
#	if transitive: r += chr(0x40)
#	return ExtendedCommunity(r + chr(subtype) + ''.join([chr(c) for c in data[:6]]))

# See RFC4360
# 0x00, 0x02 Number is administrated by a global authority
# Format is asn:route_target (2 bytes:4 bytes)
# 0x01, Number is administered by the ASN owner
# Format is ip:route_target  (4 bytes:2 bytes)
# 0x02 and 0x03 .. read the RFC :)
