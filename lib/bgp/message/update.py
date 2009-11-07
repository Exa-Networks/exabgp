#!/usr/bin/env python
# encoding: utf-8
"""
update.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import math

from bgp.display import Display

from bgp.structure.network import *
from bgp.structure.message import *

def _defix (self,data):
	l = unpack('!H',data[0:2])[0]
	return l,data[2:l+2],data[l+2:]

def new_Update (self,data):
		length = len(data)
		# withdrawn
		lw,withdrawn,data = _defix(data)
		if len(withdrawn) != lw:
			raise SendNotification(3,1)
		la,announced,nlri = _defix(data)
		if len(announced) != la:
			raise SendNotification(3,1)
		if 2 + lw + 2+ la + len(nlri) != length:
			raise SendNotification(3,1)

		# The RFC check ...
		#if lw + la + 23 > length:
		#	raise SendNotification(3,1)
		
#		print 'w   ', [hex(ord(c)) for c in withdrawn]
#		print 'pa  ', [hex(ord(c)) for c in announce]
#		print 'nlri', [hex(ord(c)) for c in nlri]

		remove = []
		while withdrawn:
			route = new_NLRI(withdrawn)
			withdrawn = withdrawn[len(route):]
			remove.append(route)
			self.logIf(True,'removing route %s' % str(route))

		add = []
		while announced:
			route = new_NLRI(announced)
			announced = announced[len(route):]
			add.append(route)
			self.logIf(True,'adding route %s' % str(route))

		#route.set_path_attribute(announce)

		routes = []
		for route in remove:
			routes.append(('-',route))
		for route in add:
			routes.append(('+',route))
		return routes

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

class Attribute (object):
	# RFC 4271
	ORIGIN           = 0x01
	AS_PATH          = 0x02
	NEXT_HOP         = 0x03
	MULTI_EXIT_DISC  = 0x04
	LOCAL_PREFERENCE = 0x05
	ATOMIC_AGGREGATE = 0x06
	AGGREGATOR       = 0x07
	# RFC 1997
	COMMUNITY        = 0x08
	# RFC 4760
	MP_REACH_NLRI    = 0x0e # 14
	MP_UNREACH_NLRI  = 0x0f # 15

	def __init__ (self,value):
		self.value = value

	def __str__ (self):
		if self.value == 0x01: return "ORIGIN"
		if self.value == 0x02: return "AS_PATH"
		if self.value == 0x03: return "NEXT_HOP"
		if self.value == 0x04: return "MULTI_EXIT_DISC"
		if self.value == 0x05: return "LOCAL_PREFERENCE"
		if self.value == 0x06: return "ATOMIC_AGGREGATE"
		if self.value == 0x07: return "AGGREGATOR"
		if self.value == 0x08: return "COMMUNITY"
		if self.value == 0x0e: return "MP_REACH_NLRI"
		if self.value == 0x0f: return "MP_UNREACH_NLRI"
		return 'UNKNOWN ATTRIBUTE (%s)' % hex(self.value)

# =================================================================== Attributes

def new_Attributes (data):
	attributes = Attributes()
	attributes.new(data)

class Attributes (dict):
	def add (self,attribute):
		typ = attribute.ID
		multi = attribute.MULTIPLE
		if attribute.MULTIPLE:
			if typ not in self.attributes:
				self[typ] = []
			self[typ].append(attribute)
		else:
			self[typ] = attribute
	
	def new (self,data):
		if not data:
			return self
	
		# We do not care if the attribute are transitive or not as we do not redistribute
		flag = Flag(ord(data[0]))
		code = Attribute(ord(data[1]))
	
		if flag & Flag.EXTENDED_LENGTH:
			length = unpack('!H',data[2:4])[0]
			offset = 4
		else:
			length = ord(data[2])
			offset = 3

		data = data[offset:]

		if not length:
			return self.new(data[length:])
	
		if code == ORIGIN:
			self.attributes.add(new_Origin(data))
			return self.new(data[length:])
		
		if code == AS_PATH:
			self.attributes.add(new_ASPath(data))
			return self.new(data[length:])
		
		if code == NEXT_HOP:
			self.attributes.add(NextHop(data))
			return self.new(data[length:])
		
		if code == MULTI_EXIT_DISC:
			self.attributes.add(MED(data))
			return self.new(data[length:])
		
		if code == LOCAL_PREFERENCE:
			self.attributes.add(LocalPreference(data))
			return self.new(data[length:])
		
		if code == ATOMIC_AGGREGATE:
			# ignore
			return self.new(data[length:])
		
		if code == AGGREGATOR:
			# content is 6 bytes
			return self.new(data[length:])

		if code == COMMUNITY:
			self.attributes.add(Communities(data))
			return self.new(data[length:])
		
		if code == MP_UNREACH_NLRI:
			afi = AFI(unpack('!H',data[offset:offset+2])[0])
			offset += 2
			safi = SAFI(ord(data[offset]))
			offset += 1
			# XXX: See RFC 5549 for better support
			if not afi in (AFI.ipv4,AFI.ipv6) or safi != SAFI.unicast:
				self.log('we only understand IPv4/IPv6 and should never have received this route (%s %s)' % (afi,safi))
				return
			data = data[offset:]
			while data:
				nlri = new_NLRI(nlri,afi)
				data = data[len(nlri):]
				self.add.append(nlri)
				self.log('removing MP nlri %s' % str(nlri))
			return self.new(data)
		
		if code == MP_REACH_NLRI:
			afi = AFI(unpack('!H',data[offset:offset+2])[0])
			offset += 2
			safi = SAFI(ord(data[offset]))
			offset += 1
			if not afi in (AFI.ipv4,AFI.ipv6) or safi != SAFI.unicast:
				self.log('we only understand IPv4/IPv6 and should never have received this route (%s %s)' % (afi,safi))
				return
			len_nh = ord(data[offset])
			offset += 1
			if afi == AFI.ipv4 and not len_nh != 4:
				# We are not following RFC 4760 Section 7 (deleting route and possibly tearing down the session)
				self.log('bad IPv4 next-hop length (%d)' % len_nh)
				return
			if afi == AFI.ipv6 and not len_nh in (16,32):
				# We are not following RFC 4760 Section 7 (deleting route and possibly tearing down the session)
				self.log('bad IPv6 next-hop length (%d)' % len_nh)
				return
			nh = data[offset:offset+len_nh]
			if len_nh == 32:
				# we have a link-local address in the next-hop we ideally need to ignore
				if nh[0] == 0xfe: nh = nh[16:]
				elif nh[16] == 0xfe: nh = nh[:16]
				# We are not following RFC 4760 Section 7 (deleting route and possibly tearing down the session)
				else: return
			nh = socket.inet_ntop(socket.AF_INET6 if len_nh >= 16 else socket.AF_INET,nh)
			offset += len_nh
			nb_snpa = ord(data[offset])
			offset += 1
			snpas = []
			for i in range(nb_snpa):
				len_snpa = ord(offset)
				offset += 1
				snpas.append(data[offset:offset+len_snpa])
				offset += len_snpa
			nlri = data[offset:]
			while nlri:
				#self.hexdump(nlri)
				route,nlri = self.read_bgp(nlri,afi)
				route.set_next_hop(nh)
				mp.append(('+',route))
				self.log('adding MP route %s' % str(route))
			return mp
			
		else:
			import warnings
			warnings.warn(str(Attribute(code)))
			return self.new(data[length:])

		return
	

# =================================================================== Origin (1)

def newOrigin (data):
	return Origin(ord(data[0]))

class Origin (int):
	ID = Attribute.ORIGIN
	MULTIPLE = False
	
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

	def __len__ (self):
		return 1

# =================================================================== ASPath (2)

def new_ASPath (data):
	stype = ord(data[0])
	slen = ord(data[1])
	sdata = data[2:2+(slen*2)]

	ASPS = ASPath(stype)
	for c in unpack('!'+('H'*slen),sdata):
		ASPS.append(c)
	return ASPS

class ASPATH (int):
	AS_SET      = 0x01
	AS_SEQUENCE = 0x02

	def __str__ (self):
		if self.type == 0x01: return 'AS_SET'
		if self.type == 0x02: return 'AS_SEQUENCE'
		return 'INVALID'

class ASPath (object):
	ID = Attribute.AS_PATH          
	MULTIPLE = False

	def __init__ (self,asptype,aspsegment = []):
		self.type = asptype
		self.segment = aspsegment
	
	def append (self,community):
		self.segment.append(community)
	
	def pack (self):
		return chr(self.type) + chr(len(self.segment)) + ''.join([community.pack() for community in self.segment])
		
	def __len__ (self):
		return 2 + (len(self.segment)*2)

	def __str__ (self):
		if len(self) >  1: return '[ %s ]' % ' '.join([str(community) for community in self])
		if len(self) == 1: return str(self[0])
		return ''

# =================================================================== NextHop (3)
# XXX: WE STILL USE IP IN THE CODE


def new_NextHop4 (data):
	nhn = unpack('!L',data[offset:offset+length])[0]
	next_hop = "%d.%d.%d.%d" % (nhn>>24,(nhn>>16)&0xFF,(nhn>>8)&0xFF,nhn&0xFF)
	return NextHop4(next_hop,AFI.ipv4,SAFI.unicast)

def new_NextHop6 (self,data):
	raise NotImplemented('not yet ...')

class NextHop4 (IPv4):
	ID = Attribute.NEXT_HOP
	MULTIPLE = False

# =================================================================== MED (4)

def new_LocalPreference (data):
	return MED(unpack('!L',data[:4])[0])

class MED (long):
	ID = Attribute.MULTI_EXIT_DISC  
	MULTIPLE = False

	def pack (self):
		return pack('!L',self)

	def __len__ (self):
		return 4

# =================================================================== Local Preference (5)

def new_LocalPreference (data):
	return LocalPreference(unpack('!L',data[:4])[0])

class LocalPreference (long):
	ID = Attribute.LOCAL_PREFERENCE 
	MULTIPLE = False

	def pack (self):
		return pack('!L',self)

	def __len__ (self):
		return 4

# =================================================================== Aggregate (6)
# we do not pass routes to other speakers, so we do not care (but could).

# =================================================================== Aggregator (7)
# we do not pass routes to other speakers, so we do not care (but could).

# =================================================================== Community (8)

def new_Communities (data):
	communities = Communities()
	while data:
		community = unpack('!L',data)
		data = data[2:]
		Communities.append(Community(community))
	return communities

class Community (long):
	def pack (self):
		return pack('!L',self)

	def __str__ (self):
		return "%d:%d" % (self >> 16, self & 0xFFFF)

	def __len__ (self):
		return 4

class Communities (list):
	ID = Attribute.COMMUNITY        
	MULTIPLE = False

	def __str__ (self):
		if len(self) > 1:
			return "[ %s ]" % " ".join(str(community) for community in self)
		return str(self[0])
		
# =================================================================== Unreacheable NLRI (14)

def new_MPUnreachNLRI (data):
		# We are not creating AFI and SAFI instances here ..
		afi,safi = unpack('!HB',data)
		offset += 3
		# XXX: See RFC 5549 for better support
		if not afi in (AFI.ipv4,AFI.ipv6) or safi != SAFI.unicast:
			self.log('we only understand IPv4/IPv6 and should never have received this route (%s %s)' % (afi,safi))
			return
		data = data[offset:]
		while data:
			nlri = new_NLRI(nlri,afi)
			data = data[len(nlri):]
			self.append(nlri)
			self.log('removing MP nlri %s' % str(nlri))
		return self.new(data)

class MPURNLRI (list):
	ID = Attribute.MP_UNREACH_NLRI  
	MULTIPLE = True

# =================================================================== Unreacheable NLRI (14)

class MPRNLRI (list):
	ID = Attribute.MP_REACH_NLRI    
	MULTIPLE = True

# =================================================================== Route

class Route (object):
	def __init__ (self,nlri):
		self.nlri = nlri
		self.next_hop = new_IP('0.0.0.0')
		self.attributes = Attributes()

	def get_next_hop (self):
		return self._next_hop
	def set_next_hop (self,ip):
		self._next_hop = new_IP(ip)
	next_hop = property(get_next_hop,set_next_hop)

	def __cmp__ (self,other):
		return \
			self.nlri == other.nlri and \
			self.next_hop == other.next_hop and \
			self.attributes == other.attributes

	def __str__ (self):
		local_pref= ''
		if self.attributes.has_key(Attribute.LOCAL_PREFERENCE):
			l = self.attributes[Attribute.LOCAL_PREFERENCE]
			if l == 100: # XXX: Double check default Local Pref
				local_pref= ' local_preference %s' % l
		
		communities = ''
		if self.attributes.has_key(Attribute.COMMUNITY):
			communities = ' community %s' % str(self.attributes[Attribute.COMMUNITY])
		
		return "'%s next-hop %s%s%s" % \
		(
			str(self.nlri),self.next_hop,
			local_pref, communities
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
		message += self._attribute(Flag.TRANSITIVE,ORIGIN,Origin(Origin.IGP).pack())
		message += self._attribute(Flag.TRANSITIVE,AS_PATH,'' if local_asn == peer_asn else self._segment(ASPath.AS_SEQUENCE,[local_asn]))
		if local_asn == peer_asn:
			message += self._attribute(Flag.TRANSITIVE,LOCAL_PREFERENCE,self.local_preference.pack())
		message += self._attribute(Flag.TRANSITIVE|Flag.OPTIONAL,COMMUNITY,''.join([c.pack() for c in self.communities])) if self.communities else ''
		# we do not store or send MED
		if self.ip.version == 4:
			message += self._attribute(Flag.TRANSITIVE,NEXT_HOP,self.next_hop.pack())
		if self.ip.version == 6:
			if mp_action == '-':
				attr = AFI(AFI.ipv6).pack() + SAFI(SAFI.unicast).pack() + Prefix.pack(self)
				message += self._attribute(Flag.TRANSITIVE,MP_UNREACH_NLRI,attr)
			if mp_action == '+':
				prefix = Prefix.bgp(self)
				next_hop = self.next_hop.pack()
				attr = AFI(AFI.ipv6).pack() + SAFI(SAFI.unicast).pack() + chr(len(next_hop)) + next_hop + chr(0) + prefix
				message += self._attribute(Flag.TRANSITIVE,MP_REACH_NLRI,attr)
		return message


