#!/usr/bin/env python
# encoding: utf-8
"""
data.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

HOLD_TIME=180

import time
import socket
from struct import pack,unpack
	# !L : Network Long  (4 bytes)
	# !H : Network Short (2 bytes)
import StringIO


class IP (long):
	regex_ipv4 = '(?:\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])\.(?:\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])\.(?:\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])\.(?:\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])'

	def __new__ (cls,ip):
		try:
			addr = unpack('>L',socket.inet_aton(ip))[0]
		except socket.error:
			raise ValueError('"%s" is an invalid address' % str(ip))
		except TypeError:
			addr = long(ip)
		return long.__new__(cls,addr) 

	def pack (self):
		return pack('!L',self)

	# remove this HORRIBLE function and use __str__ instead
	def human (self):
		return "%s.%s.%s.%s" % (self>>24, self>>16&0xFF, self>>8&0xFF, self&0xFF)

	def __len__ (self):
		return 4

class Mask (int):
	regex_mask = '(?:\d|[12]\d|3[012])'
	slash_to_size = dict([(32-bits,(1<<bits)) for bits in range(0,33)])
	mask_to_slash = dict([((1L<<32) - (1<<bits),32-bits) for bits in range(0,33)])
	range_to_slash = dict([("%d.%d.%d.%d" % (k>>24, k>>16 & 0xFF ,k>>8 & 0xFF, k&0xFF),mask_to_slash[k]) for k in mask_to_slash.keys()])
	slash_to_mask = dict([(32-bits,(1L<<32) - (1<<bits)) for bits in range(0,33)])

	def __new__ (cls,mask):
		try:
			slash = int(mask)
		except ValueError:
			try:
				slash = cls.range_to_slash[mask]
			except KeyError:
				raise ValueError('the netmask is invalid %s' % str(mask))
		
		if not slash in range(0,33):
			return ValueError('the netmask is invalid /%s' % str(slash))

		return int.__new__(cls,slash)
	
	def pack (self):
		return chr(self)
	
	def __len__ (self):
		return 1

class Prefix (IP):
	# format is (version,address,slash)
	def __new__ (cls,ip,mask):
		new = IP.__new__(cls,ip)
		new.mask = Mask(mask)
		return new
	
	@property
	def version (self):
		return 4
	
	@property
	def name (self):
		return IP(self)
	
	@property
	def length (self):
		return self.mask
	
	@property
	def raw (self):
		return (4,long(self),int(self.mask))
	
	def human (self):
		return "%s/%d" % (IP.human(self),self.mask)
	
	def bgp (self):
		ip = IP(self)
		if self.mask > 24: return "%s%s" % (self.mask.pack(),ip.pack())
		if self.mask > 16: return "%s%s" % (self.mask.pack(),ip.pack()[:3])
		if self.mask >  8: return "%s%s" % (self.mask.pack(),ip.pack()[:2])
		if self.mask >  0: return "%s%s" % (self.mask.pack(),ip.pack()[:1])
		return '\0'

	# XXX: This perform no boundary check as it is only used for debugging atm
	def unpack (stream):
		mask = ord(stream.read(1))
		if mask > 24: data = stream.read(4)
		if mask > 16: data = stream.read(3)+'\0'
		if mask >  8: data = stream.read(2)+'\0\0'
		if mask >  0: data = stream.read(1)+'\0\0\0'
		if mask == 0: data = '\0\0\0\0'
		return Prefix(unpack('!L')[0],mask)

class RouterID (IP):
	pass

class Version (int):
	def pack (self):
		return chr(self)

class ASN (int):
	regex = "(?:0[xX][0-9a-fA-F]{1,8}|\d+:\d+|\d+)"
	
	def __new__ (cls,asn):
		try:
			value = int(asn)
		except ValueError:
			value = int(asn,16)
		if value >= (1<<16):
			raise ValueError('ASN is too big')
		return int.__new__(cls,value)
	
	def pack (self):
		return pack('!H',self)

	def __len__ (self):
		return 2

class Community (long):
	def __new__ (cls,data):
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
				
		return long.__new__(cls,value)
	
	def pack (self):
		return pack('!L',self)
	
	def __str__ (self):
		return "%d:%d" % (self >> 16, self & 0xFFFF)
	
	def __len__ (self):
		return 4


class Communities (list):
	def append (self,data):
		list.append(self,Community(data))
		self.sort()

	def pack (self):
		return ''.join([community.pack() for community in self])
		
	def __str__ (self):
		if len(self) >  1: return '[ %s ]' % ' '.join([str(community) for community in self])
		if len(self) == 1: return str(self[0])
		return ''

class LocalPreference (long):
	def pack (self):
		return pack('!L',self)
	
	def __len__ (self):
		return 4

class HoldTime (int):
	def update (self,value):
		if value < 3: return
		if value < self:
			self = value
	
	def pack (self):
		return pack('!H',self)

	def keepalive (self):
		return int(self/3)

	def __len__ (self):
		return 2

		class Flag (int):
			EXTENDED_LENGTH = 16
			PARTIAL = 32
			TRANSITIVE = 64
			OPTIONAL = 128

			def __str__ (self):
				if self ==  16: return "EXTENDED_LENGTH"
				if self ==  32: return "PARTIAL"
				if self ==  64: return "TRANSITIVE"
				if self == 128: return "OPTIONAL"
				return 'UNKNOWN'

class Origin (int):
	IGP = 0
	EGP = 1
	INCOMPLETE = 2

	def __str__ (self):
		if self == 0: return 'IGP'
		if self == 1: return 'EGP'
		if self == 2: return 'INCOMPLETE'
		return 'INVALID'

class ASPath (int):
	AS_SET = 1
	AS_SEQUENCE = 2

	def __str__ (self):
		if self == 1: return 'AS_SET'
		if self == 2: return 'AS_SEQUENCE'
		return 'INVALID'

class Attribute (int):
	ORIGIN = 1
	AS_PATH = 2
	NEXT_HOP = 3
	MULTI_EXIT_DISC = 4
	LOCAL_PREFERENCE = 5
	ATOMIC_AGGREGATE = 6
	AGGREGATOR = 7
	COMMUNITY = 8

	def __str__ (self):
		if self ==  1: return "ORIGIN"
		if self ==  2: return "AS_PATH"
		if self ==  3: return "NEXT_HOP"
		if self ==  4: return "MULTI_EXIT_DISC"
		if self ==  5: return "LOCAL_PREFERENCE"
		if self ==  6: return "ATOMIC_AGGREGATE"
		if self ==  7: return "AGGREGATOR"
		if self ==  8: return "COMMUNITY"
		return 'UNKNOWN'


class Route (Prefix):
	def __new__ (cls,ip,slash,next_hop=''):
		new = Prefix.__new__(cls,ip,slash)
		if next_hop: new.next_hop = next_hop
		else: new.next_hop = ip
		new._local_preference = LocalPreference(100)
		new.communities = Communities()
		return new

	@property
	def next_hop (self):
		return self._next_hop

	@next_hop.setter
	def next_hop (self,ip):
		self._next_hop = Prefix(ip,'32')

	@property
	def local_preference (self):
		return self._local_preference

	@local_preference.setter
	def local_preference (self,preference):
		self._local_preference = LocalPreference(preference)

	def __cmp__ (self,other):
		return \
			self.raw == other.raw and \
			self.next_hop == other.next_hop and \
			self.local_preference == other.local_preference and \
			self.communities == other.communities

	def __str__ (self):
		return "%s/%s next-hop %s%s%s" % \
		(
			self.human(),
			self.length,
			self.next_hop.human(),
			" local_preference %d" % self.local_preference if self.local_preference != 100 else '',
			" community %s" % self.communities if self.communities else ''
		)

	def _attribute (self,attr_flag,attr_type,value):
		return "%s%s%s%s" % (chr(attr_flag),chr(attr_type),chr(len(value)),value)
	
	def _segment (self,seg_type,values):
		if len(values)>255:
			return self._segment(values[:256]) + self._segment(values[256:])
		return "%s%s%s" % (seg_type,chr(len(values)),''.join([v.pack() for v in values]))
	
	def pack (self,local_asn,peer_asn):
		message = ''
		message += self._attribute(Flag.TRANSITIVE,Attribute.ORIGIN,chr(Origin.IGP))
		message += self._attribute(Flag.TRANSITIVE,Attribute.AS_PATH,'' if local_asn == peer_asn else self._segment(ASPath.AS_SEQUENCE,[local_asn]))
		message += self._attribute(Flag.TRANSITIVE,Attribute.NEXT_HOP,self.next_hop.name.pack())
		if local_asn == peer_asn:
			message += self._attribute(Flag.TRANSITIVE,Attribute.LOCAL_PREFERENCE,self.local_preference.pack())
		message += self._attribute(Flag.TRANSITIVE|Flag.OPTIONAL,Attribute.COMMUNITY,''.join([c.pack() for c in self.communities])) if self.communities else ''
		message += self.bgp()
		
		return message

	# XXX: only for debugging does not do bound checking correctly
	def unpack (stream):
		l,data = self._defix(stream)
		if len(data) != l:
			print "buffer underrun in Route"
		announced = StringIO(data)
		while not announced.eof():
			length = ord(announced.read(1))
			data = announced.read(length)
			flag = data[0]
			code = data[1]
			
			if code == Attribute.ORIGIN:
				origin = data[2]
				print 'orgin is', Orgin(orgin)
			if code == Attribute.AS_PATH:
				pass
			if code == Attribute.NEXT_HOP:
				next_hop = unpack('!L',data[2:])[0]
				print 'next hop is', IP(next_hop)
		
# The definition of a neighbor (from reading the configuration)

class Neighbor (object):
	def __init__ (self):
		self.description = ''
		self._router_id = None
		self.local_address = None
		self.peer_address = None
		self.peer_as = None
		self.local_as = None
		self.hold_time = HoldTime(HOLD_TIME)
		self.routes = []

	def missing (self):
		if self.local_address is None: return 'local-address'
		if self.peer_address is None: return 'peer-address'
		if self.local_as is None: return 'local-as'
		if self.peer_as is None: return 'peer-as'
		return ''

	@property
	def router_id (self):
		return self._router_id if self._router_id else self.local_address

	@router_id.setter
	def router_id (self,value):
		self._router_id = value
	
	def __eq__ (self,other):
		return \
			self._router_id == other._router_id and \
			self.local_address == other.local_address and \
			self.local_as == other.local_as and \
			self.peer_address == other.peer_address and \
			self.peer_as == other.peer_as
	
	def __ne__(self, other):
		return not (self == other)
	
	def __str__ (self):
		return """\
neighbor %s {
	description "%s";
	router-id %s;
	local-address %s;
	local-as %d;
	peer-as %d;
	static {%s
	}
}""" % (
	self.peer_address.human(),
	self.description,
	self.router_id.human(),
	self.local_address.human(),
	self.local_as,
	self.peer_as,
	'\n\t\t' + '\n\t\t'.join([str(route) for route in self.routes]) if self.routes else ''
)

