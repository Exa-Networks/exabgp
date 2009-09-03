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

def dump (data):
	print [hex(ord(c)) for c in data]

class Container (object):
	def __init__ (self,value):
		self.value = value
	def __lt__(self, other):
		return self.value < other
	def __le__(self, other):
		return self.value <= other
	def __eq__(self, other):
		return self.value == other
	def __ne__(self, other):
		return self.value != other
	def __gt__(self, other):
		return self.value > other
	def __ge__(self, other):
		return self.value >= other
	def __cmp__(self,other):
		return cmp(self.value,other)
	def __hash__(self):
		return hash(self.value)
	def __nonzero__(self):
		return self.value != 0
	def __unicode__(self):
		return unicode(self.value)
	def __str__(self):
		return str(self.value)
	def __repr__(self):
		return repr(self.value)
	def __len__(self):
		return len(self.value)
	def __contains__(self,item):
		return item in self.value
	def __iter__ (self):
		return iter(self.value)
	def __reversed__(self):
		return self.value.reversed()
	def __setitem__(self, key, value):
		self.value[key] = value
	def __delitem__(self, key):
		del self.value[key]

class IP (Container):
	regex_ipv4 = '(?:\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])\.(?:\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])\.(?:\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])\.(?:\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])'

	def __init__ (self,ip):
		try: 
			Container.__init__(self,unpack('>L',socket.inet_aton(ip))[0])
		except socket.error:
			raise ValueError('"%s" is an invalid address' % str(ip))
		except TypeError:
			Container.__init__(self,long(ip))
	
	def pack (self):
		return pack('!L',self.value)

	def human (self):
		return "%s.%s.%s.%s" % (self.value>>24, self.value>>16&0xFF, self.value>>8&0xFF, self.value&0xFF)

	def __len__ (self):
		return 4

class Mask (Container):
	regex_mask = '(?:\d|[12]\d|3[012])'
	slash_to_size = dict([(32-bits,(1<<bits)) for bits in range(0,33)])
	mask_to_slash = dict([((1L<<32) - (1<<bits),32-bits) for bits in range(0,33)])
	range_to_slash = dict([("%d.%d.%d.%d" % (k>>24, k>>16 & 0xFF ,k>>8 & 0xFF, k&0xFF),mask_to_slash[k]) for k in mask_to_slash.keys()])
	slash_to_mask = dict([(32-bits,(1L<<32) - (1<<bits)) for bits in range(0,33)])

	def __init__ (self,mask):
		if mask.isdigit():
			slash = int(mask)
			Container.__init__(self,slash)
		else:
			try: Container.__init__(self,self.range_to_slash[mask])
			except KeyError: raise ValueError('the netmask is invalid %s' % str(mask))
		if not self.value in range(0,33):
			return ValueError('the netmask is invalid /%s' % str(slash))
	
	def pack (self):
		return chr(self.value)
	
	def __len__ (self):
		return 1

class Prefix (Container):
	# format is (version,address,slash)
	def __init__ (self,ip,mask):
		Container.__init__(self,(4,IP(ip),Mask(mask)))

	@property
	def version (self):
		return self.value[0]
	
	@property
	def name (self):
		return self.value[1]
	
	@property
	def length (self):
		return self.value[2]
	
	@property
	def raw (self):
		return self.value
	
	def human (self):
		return "%s/%d" % (self.name.human(),self.length.value)
	
	def bgp (self):
		if self.value[2].value > 24: return "%s%s" % (self.value[2].pack(),self.value[1].pack())
		if self.value[2].value > 16: return "%s%s" % (self.value[2].pack(),self.value[1].pack()[:3])
		if self.value[2].value >  8: return "%s%s" % (self.value[2].pack(),self.value[1].pack()[:2])
		if self.value[2].value >  0: return "%s%s" % (self.value[2].pack(),self.value[1].pack()[:1])
		return '\0'
	

class RouterID (IP):
	def __init__ (self,ip):
		IP.__init__(self,ip)

class Version (int):
	def pack (self):
		return chr(self)

class ASN (int):
	regex = "(?:0[xX][0-9a-fA-F]{1,8}|\d+:\d+|\d+)"
	
	def pack (self):
		return pack('!H',self)

	def __len__ (self):
		return 2

class Community (Container):
	def __init__(self,data):
		separator = data.find(':')
		if separator > 0:
			value = (long(data[:separator])<<16) + long(data[separator+1:])
		elif len(data) >=2 and data[1] in 'xX':
			value = int(data,16)
		else:
			value = long(data)
		Container.__init__(self,value)
	
	def pack (self):
		return pack('!L',self.value)
	
	def __str__ (self):
		return "%d:%d" % (self.value >> 16, self.value & 0xFFFF)
	
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

class Route (Prefix):
	def __init__ (self,ip,slash,next_hop=''):
		Prefix.__init__(self,ip,slash)
		if next_hop: self.next_hop = next_hop
		else: self.next_hop = ip
		self._local_preference = LocalPreference(100)
		self.communities = Communities()

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
			self.raw() == other.raw() and \
			self.next_hop == other.next_hop and \
			self.local_preference == other.local_preference and \
			self.communities == other.communities

	def __repr__ (self):
		return str(self)

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
		TRANSITIVE = Message.Attribute.TRANSITIVE
		OPTIONAL = Message.Attribute.OPTIONAL
		
		ORIGIN = Message.Attribute.ORIGIN
		NEXT_HOP = Message.Attribute.NEXT_HOP
		LOCAL_PREF = Message.Attribute.LOCAL_PREFERENCE
		AS_PATH = Message.Attribute.AS_PATH
		COMMUNITY = Message.Attribute.COMMUNITY

		AS_SEQUENCE = Message.Attribute.ASPath.AS_SEQUENCE

		message = ''
		message += self._attribute(TRANSITIVE,ORIGIN,chr(Message.Attribute.Origin.IGP))
		message += self._attribute(TRANSITIVE,AS_PATH,'' if local_asn == peer_asn else self._segment(AS_SEQUENCE,[local_asn]))
		message += self._attribute(TRANSITIVE,NEXT_HOP,self.next_hop.name.pack())
		if local_asn == peer_asn:
			message += self._attribute(TRANSITIVE,LOCAL_PREF,self.local_preference.pack())
		message += self._attribute(TRANSITIVE|OPTIONAL,COMMUNITY,''.join([c.pack() for c in self.communities])) if self.communities else ''
		return message
		
class State (object):
	IDLE = 1
	CONNECT = 2
	ACTIVE = 3
	OPENSENT = 4
	OPENCONFIRM = 5
	ESTABLISHED = 6

class Message (object):
	TYPE = 0
	
	MARKER = chr(0xff)*16
	
	class Type:
		OPEN = 1,
		UPDATE = 2,
		NOTIFICATION = 4,
		KEEPALIVE = 8,
		ROUTE_REFRESH = 16,
		LIST = 32,
		HEADER = 64,
		GENERAL = 128,
		#LOCALRIB = 256,

	class Attribute:
		class Origin:
			IGP = 0
			EGP = 1
			INCOMPLETE = 2

		class ASPath:
			AS_SET = 1
			AS_SEQUENCE = 2

		ORIGIN = 1
		AS_PATH = 2
		NEXT_HOP = 3
		MULTI_EXIT_DISC = 4
		LOCAL_PREFERENCE = 5
		ATOMIC_AGGREGATE = 6
		AGGREGATOR = 7
		COMMUNITY = 8

		EXTENDED_LENGTH = 16
		PARTIAL = 32
		TRANSITIVE = 64
		OPTIONAL = 128
	
	def _message (self,message = ""):
		message_len = pack('!H',19+len(message))
		return "%s%s%s%s" % (self.MARKER,message_len,self.TYPE,message)

# This message is not part of the RFC but very practical to return that no data is waiting on the socket
class NOP (Message):
	TYPE = chr(0)

class Open (Message):
	TYPE = chr(1)

	def __init__ (self,asn,router_id,hold_time=HOLD_TIME,version=4):
		self.version = Version(version)
		self.asn = ASN(asn)
		self.hold_time = HoldTime(hold_time)
		self.router_id = RouterID(router_id)

	def message (self):
		return self._message("%s%s%s%s%s" % (self.version.pack(),self.asn.pack(),self.hold_time.pack(),self.router_id.pack(),chr(0)))

	def __str__ (self):
		return "OPEN version=%d asn=%d hold_time=%s router_id=%s" % (self.version, self.asn, self.hold_time, self.router_id)

class Update (Message):
	TYPE = chr(2)

	def __init__ (self,table):
		self.table = table
		self.last = 0

	def _prefix (self,data):
		return '%s%s' % (pack('!H',len(data)),data)

	def announce (self,local_asn,remote_asn):
		announce = []
		# table.changed always returns routes to remove before routes to add
		for action,route in self.table.changed(self.last):
			if action == '+':
				w = self._prefix(route.bgp())
				a = self._prefix(route.pack(local_asn,remote_asn))+route.bgp()
				announce.append(self._message(w + a))
			if action == '':
				self.last = route

		return ''.join(announce)

	def update (self,local_asn,remote_asn):
		announce = []
		withdraw = {}
		# table.changed always returns routes to remove before routes to add
		for action,route in self.table.changed(self.last):
			if action == '-':
				withdraw[route.raw] = route.bgp()
			if action == '+':
				raw = route.raw
				if withdraw.has_key(raw):
					del withdraw[raw]
				w = self._prefix(route.bgp())
				a = self._prefix(route.pack(local_asn,remote_asn))
				announce.append(self._message(w + a))
			if action == '':
				self.last = route
			
		if len(withdraw.keys()) == 0 and len(announce) == 0:
			return ''
		
		unfeasible = self._message(self._prefix(''.join([withdraw[raw] for raw in withdraw.keys()])) + self._prefix(''))
		return unfeasible + ''.join(announce)
	

	def __str__ (self):
		return "UPDATE"


class Failure (Exception):
	pass

# A Notification received from our peer.
# RFC 1771 Section 4.5 - but really I should refer to RFC 4271 Section 4.5 :)
class Notification (Message,Failure):
	TYPE = chr(3)
	
	_str_code = [
		"",
		"Message header error",
		"OPEN message error",
		"UPDATE message error", 
		"Hold timer expired",
		"State machine error",
		"Cease"
	]

	_str_subcode = {
		1 : {
			0 : "Unspecific.",
			1 : "Connection Not Synchronized.",
			2 : "Bad Message Length.",
			3 : "Bad Message Type.",
		},
		2 : {
			0 : "Unspecific.",
			1 : "Unsupported Version Number.",
			2 : "Bad Peer AS.",
			3 : "Bad BGP Identifier.",
			4 : "Unsupported Optional Parameter.",
			5 : "Authentication Notification (Deprecated).",
			6 : "Unacceptable Hold Time.",
		},
		3 : {
			0 : "Unspecific.",
			1 : "Malformed Attribute List.",
			2 : "Unrecognized Well-known Attribute.",
			3 : "Missing Well-known Attribute.",
			4 : "Attribute Flags Error.",
			5 : "Attribute Length Error.",
			6 : "Invalid ORIGIN Attribute.",
			7 : "AS Routing Loop.",
			8 : "Invalid NEXT_HOP Attribute.",
			9 : "Optional Attribute Error.",
			10 : "Invalid Network Field.",
			11 : "Malformed AS_PATH.",
		},
		4 : {
			0 : "Hold Timer Expired.",
		},
		5 : {
			0 : "Finite State Machine Error.",
		},
		6 : {
			0 : "Cease.",
		},
	}
	
	def __init__ (self,code,subcode,data=''):
		assert self._str_subcode.has_key(code)
		assert self._str_subcode[code].has_key(subcode)
		self.code = code
		self.subcode = subcode
		self.data = data
	
	def __str__ (self):
		return "%s: %s" % (self._str_code[self.code], self._str_subcode[self.code][self.subcode])

# A Notification we need to inform our peer of.
class SendNotification (Notification):
	def message (self):
		return self._message("%s%s%s" % (chr(self.code),chr(self.subcode),self.data))

class KeepAlive (Message):
	TYPE = chr(4)
	
	def message (self):
		return self._message()

	def __str__ (self):
		return "KEEPALIVE (%s)" % time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime())

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
