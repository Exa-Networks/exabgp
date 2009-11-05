#!/usr/bin/env python
# encoding: utf-8
"""
update.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import math

from bgp.structure.family  import *
from bgp.structure.network import *
from bgp.structure.message import *

class Update (Message):
	TYPE = chr(0x02)

	def __init__ (self,table):
		self.table = table
		self.last = 0

	def announce (self,local_asn,remote_asn):
		return self.update(local_asn,remote_asn,False)

	def update (self,local_asn,remote_asn,remove=True):
		message = ''
		withdraw4 = {}
		announce4 = []
		mp_route6 = []
		# table.changed always returns routes to remove before routes to add
		for action,route in self.table.changed(self.last):
			if action == '':
				self.last = route
				continue
			if route.ip.version == 6:
				# XXX: We should keep track of what we have already sent to only remove routes if we have sent them
				if remove:
					mp_route6.append(self._message(self._prefix('') + self._prefix(route.pack(local_asn,remote_asn,'-'))))
				if action == '+':
					mp_route6.append(self._message(self._prefix('') + self._prefix(route.pack(local_asn,remote_asn,'+'))))
				continue
			if route.ip.version == 4:
				if action == '-' and remove:
					prefix = str(route)
					withdraw4[prefix] = route.bgp()
					continue
				if action == '+':
					prefix = str(route)
					if withdraw4.has_key(prefix):
						del withdraw4[prefix]
					announce4.append(self._message(self._prefix(route.bgp()) + self._prefix(route.pack(local_asn,remote_asn)) + route.bgp()))
					continue
			
		if len(withdraw4.keys()) or len(announce4):
			# XXX: We should keep track of what we have already sent to only remove routes if we have sent them
			remove4 = self._message(self._prefix(''.join([withdraw4[prefix] for prefix in withdraw4.keys()])) + self._prefix(''))
			adding4 = ''.join(announce4)
			message += remove4 + adding4
		
		if len(mp_route6):
			message += ''.join(mp_route6)
		
		return message
	
	def __str__ (self):
		return "UPDATE"

# =================================================================== Flag

class Flag (int):
	EXTENDED_LENGTH = 0x10 # 16
	PARTIAL         = 0x20 # 32
	TRANSITIVE      = 0x40 # 64
	OPTIONAL        = 0x80 # 128

	def __str__ (self):
		r = []
		v = int(self)
		if v & 0x10:
			r.append("EXTENDED_LENGTH")
			v -= 0x10
		if v & 0x20:
			r.append("PARTIAL")
			v -= 0x20
		if v & 0x40:
			r.append("TRANSITIVE")
			v -= 0x40
		if v & 0x80:
			r.append("OPTIONAL")
			v -= 0x80
		if v:
			r.append("UNKNOWN %s" % hex(v))
		return " ".join(r)



# =================================================================== Attribute

class Attribute (int):
	# RFC 4271
	ORIGIN           = 0x01
	AS_PATH          = 0x02
	NEXT_HOP         = 0x03
	MULTI_EXIT_DISC  = 0x04
	LOCAL_PREFERENCE = 0x05
	ATOMIC_AGGREGATE = 0x06
	AGGREGATOR       = 0x07
	COMMUNITY        = 0x08
	# RFC 4760
	MP_REACH_NLRI    = 0x0e # 14
	MP_UNREACH_NLRI  = 0x0f # 15

	def __str__ (self):
		if self == 0x01: return "ORIGIN"
		if self == 0x02: return "AS_PATH"
		if self == 0x03: return "NEXT_HOP"
		if self == 0x04: return "MULTI_EXIT_DISC"
		if self == 0x05: return "LOCAL_PREFERENCE"
		if self == 0x06: return "ATOMIC_AGGREGATE"
		if self == 0x07: return "AGGREGATOR"
		if self == 0x08: return "COMMUNITY"
		if self == 0x0e: return "MP_REACH_NLRI"
		if self == 0x0f: return "MP_UNREACH_NLRI"
		return 'UNKNOWN'

# =================================================================== Origin

class Origin (int):
	IGP        = 0x00
	EGP        = 0x01
	INCOMPLETE = 0x02

	def __str__ (self):
		if self == 0x00: return 'IGP'
		if self == 0x01: return 'EGP'
		if self == 0x02: return 'INCOMPLETE'
		return 'INVALID'

	def pack (self):
		return chr(self)

# =================================================================== ASPath

class ASPath (int):
	AS_SET      = 0x01
	AS_SEQUENCE = 0x02

	def __str__ (self):
		if self == 0x01: return 'AS_SET'
		if self == 0x02: return 'AS_SEQUENCE'
		return 'INVALID'

# =================================================================== ASPath
# XXX: WE STILL USE IP IN THE CODE

class NextHop (IP):
	pass

# =================================================================== Local Preference

class LocalPreference (long):
	def pack (self):
		return pack('!L',self)

	def __len__ (self):
		return 4

# =================================================================== Community

class Community (long):
	def new (self,data):
		try:
			value = int(data)
		except ValueError:
			separator = data.find(':')
			if separator > 0:
				value = (long(data[:separator])<<16) + long(data[separator+1:])
			elif len(data) >=2 and data[1] in 'xX':
				value = long(data,16)
			else:
				value = long(data)
		return Community(value)

	def pack (self):
		return pack('!L',self)

	def __str__ (self):
		return "%d:%d" % (self >> 16, self & 0xFFFF)

	def __len__ (self):
		return 4

# =================================================================== Communities

class Communities (list):
	_factory = Community()

	def append (self,data):
		list.append(self,self._factory.new(data))
		self.sort()

	def pack (self):
		return ''.join([community.pack() for community in self])

	def __str__ (self):
		if len(self) >  1: return '[ %s ]' % ' '.join([str(community) for community in self])
		if len(self) == 1: return str(self[0])
		return ''

# =================================================================== Prefix

class Prefix (object):
	_factory = Mask()

	# format is (version,address,slash)
	def __init__ (self,address,mask):
		self.ip = IP(address)
		self.mask = self._factory.new(mask,self.ip.length)

	def bgp (self):
		size = int(math.ceil(float(self.mask)/8))
		return "%s%s" % (self.mask.pack(),self.ip.pack()[:size])

	def __str__ (self):
		return '%s/%d' % (self.ip,self.mask)

# =================================================================== Route
# XXX: THIS SHOULD BE CALLED NLRI

class Route (Prefix):
	def __init__ (self,ip,slash,next_hop=''):
		Prefix.__init__(self,ip,slash)
		self.next_hop = next_hop if next_hop else ip
		self.local_preference = 100
		self.communities = Communities()

	def get_next_hop (self):
		return self._next_hop
	def set_next_hop (self,ip):
		self._next_hop = IP(ip)
	next_hop = property(get_next_hop,set_next_hop)

	def get_local_preference (self):
		return self._local_preference
	def set_local_preference (self,preference):
		self._local_preference = LocalPreference(preference)
	local_preference = property(get_local_preference,set_local_preference)

	def __cmp__ (self,other):
		return \
			self.ip == other.ip and \
			self.mask == other.mask and \
			self.next_hop == other.next_hop and \
			self.local_preference == other.local_preference and \
			self.communities == other.communities

	def __str__ (self):
		return "%s next-hop %s%s%s" % \
		(
			Prefix.__str__(self),
			self.next_hop,
			" local_preference %d" % self.local_preference if self.local_preference != 100 else '',
			" community %s" % self.communities if self.communities else ''
		)

	def _attribute (self,attr_flag,attr_type,value):
		if attr_flag & Flag.OPTIONAL and not value:
			return ''
		length = len(value)
		if length > 0xFF:
			attr_flag &= Flag.EXTENDED_LENGTH
		if attr_flag & Flag.EXTENDED_LENGTH:
			len_value = pack('!H',length)[0]
		else:
			len_value = chr(length)
		return "%s%s%s%s" % (chr(attr_flag),chr(attr_type),len_value,value)

	def _segment (self,seg_type,values):
		if len(values)>255:
			return self._segment(values[:256]) + self._segment(values[256:])
		return "%s%s%s" % (chr(seg_type),chr(len(values)),''.join([v.pack() for v in values]))

	def pack (self,local_asn,peer_asn,mp_action=''):
		message = ''
		message += self._attribute(Flag.TRANSITIVE,Attribute.ORIGIN,Origin(Origin.IGP).pack())
		message += self._attribute(Flag.TRANSITIVE,Attribute.AS_PATH,'' if local_asn == peer_asn else self._segment(ASPath.AS_SEQUENCE,[local_asn]))
		if local_asn == peer_asn:
			message += self._attribute(Flag.TRANSITIVE,Attribute.LOCAL_PREFERENCE,self.local_preference.pack())
		message += self._attribute(Flag.TRANSITIVE|Flag.OPTIONAL,Attribute.COMMUNITY,''.join([c.pack() for c in self.communities])) if self.communities else ''
		# we do not store or send MED
		if self.ip.version == 4:
			message += self._attribute(Flag.TRANSITIVE,Attribute.NEXT_HOP,self.next_hop.pack())
		if self.ip.version == 6:
			if mp_action == '-':
				attr = AFI(AFI.ipv6).pack() + SAFI(SAFI.unicast).pack() + Prefix.pack(self)
				message += self._attribute(Flag.TRANSITIVE,Attribute.MP_UNREACH_NLRI,attr)
			if mp_action == '+':
				prefix = Prefix.bgp(self)
				next_hop = self.next_hop.pack()
				attr = AFI(AFI.ipv6).pack() + SAFI(SAFI.unicast).pack() + chr(len(next_hop)) + next_hop + chr(0) + prefix
				message += self._attribute(Flag.TRANSITIVE,Attribute.MP_REACH_NLRI,attr)
		return message

