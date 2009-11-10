#!/usr/bin/env python
# encoding: utf-8
"""
update.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import math

from bgp.display import Display

from bgp.message.inet import *
from bgp.message.parent import *
from bgp.message.notification import Notify

def new_Updates (data):
		length = len(data)
		# withdrawn
		lw,withdrawn,data = defix(data)
		if len(withdrawn) != lw:
			raise Notify(3,1)
		la,attribute,announced = defix(data)
		if len(attribute) != la:
			raise Notify(3,1)
		# The RFC check ...
		#if lw + la + 23 > length:
		if 2 + lw + 2+ la + len(announced) != length:
			raise Notify(3,1)

		remove = Updates()
		while withdrawn:
			nlri = new_NLRI(withdrawn)
			withdrawn = withdrawn[len(nlri):]
			remove.append(Update(nlri,'-'))
			print 'removing route %s' % str(nlri)

		updates = Updates()
		attributes = new_Attributes(attribute)

		for aid,attrs in attributes.iteritems():
			if aid == MPRNLRI.ID:
				for a in attrs:
					# XXX: not the best interface ever (.value)
					updates.append(a.value)
			if aid == MPURNLRI.ID:
				for a in attr:
					nlri = a.value.nlri
					remove.append(Update(nlri,'-'))

		while announced:
			nlri = new_NLRI(announced)
			announced = announced[len(nlri):]
			updates.append(Update(nlri,'+'))
			print 'updating route %s' % str(nlri)

		for route in updates:
			# XXX: we should really make a copy of the attribute so we can modify it later
			route.attributes = attributes

		updates.extend(remove)
		return updates

# =================================================================== Updates

class Updates (list):
	TYPE = chr(0x02)

	def __str__ (self):
		return "UPDATES [%s]" % ' '.join(str(update) for update in self)

# =================================================================== Route

class Update (Message):
	TYPE = chr(0x02)

	def __init__ (self,nlri,action='+'):
		self.nlri = nlri
		self.attributes = Attributes()
		self._next_hop6 = None
		self.action = action

	def get_next_hop (self):
		return self.attributes.get(Attribute.NEXT_HOP,None)
	def set_next_hop (self,ip):
		self.attributes[Attribute.NEXT_HOP] = NextHop(ip)
	next_hop = property(get_next_hop,set_next_hop)

	def get_next_hop6 (self):
		return self._next_hop6
	def set_next_hop6 (self,ip):
		self._next_hop6 = IPv6(ip)
	next_hop6 = property(get_next_hop6,set_next_hop6)

	def pack_attributes (self,local_asn,peer_asn):
		ibgp = local_asn == peer_asn
		# we do not store or send MED
		message = ''

		attributes = [self.attributes[a].ID for a in self.attributes]

		if Attribute.ORIGIN not in attributes:
			message += Origin(Origin.IGP).pack()

		if Attribute.AS_PATH not in attributes:
			if local_asn == peer_asn:
				message += ASPath(ASPath.AS_SEQUENCE,[]).pack()
			else:
				message += ASPath(ASPath.AS_SEQUENCE,[local_asn]).pack()

		for k,attribute in self.attributes.iteritems():
			if attribute.ID == Attribute.NEXT_HOP:
				if self.nlri.afi != AFI.ipv4 or self.next_hop6:
					continue
			if attribute.ID == Attribute.LOCAL_PREFERENCE:
				if local_asn != peer_asn:
					continue
			if attribute.ID == Attribute.AS_PATH:
				message += attribute.pack(ibgp)
				continue
			message += attribute.pack()

		return message

	def announce (self,local_asn,remote_asn):
		attributes = self.pack_attributes(local_asn,remote_asn)
		if self.nlri.afi == AFI.ipv6:
			attributes += MPURNLRI(self).pack()
			return self._message(prefix('') + prefix(attributes))
		return self._message(prefix('') + prefix(attributes) + self.nlri.pack())

	def withdraw (self,local_asn=None,remote_asn=None):
		if self.nlri.afi == AFI.ipv4:
			return self._message(prefix(self.nlri.pack()) + prefix(''))
		return self._message(prefix('') + prefix(MPURNLRI(self).pack()))

	def update (self,local_asn,remote_asn):
		attributes = self.pack_attributes(local_asn,remote_asn)
		if self.nlri.afi == AFI.ipv6:
			attributes += MPRNLRI(self).pack()
			return self._message(prefix('') + prefix(attributes))
		return self._message(prefix(self.nlri.pack()) + prefix(attributes) + self.nlri.pack())

	def __cmp__ (self,other):
		return \
			self.nlri == other.nlri \
		and self.next_hop == other.next_hop \
		and self.next_hop6 == other.next_hop6 \
#		and self.attributes == other.attributes

	def __str__ (self):
		local_pref= ''

		if self.attributes.has(Attribute.LOCAL_PREFERENCE):
			l = self.attributes[Attribute.LOCAL_PREFERENCE]
			if l == 100: # XXX: Double check default Local Pref
				local_pref= ' local_preference %s' % l

		communities = ''
		if self.attributes.has(Attribute.COMMUNITY):
			communities = ' community %s' % str(self.attributes[Attribute.COMMUNITY])

		next_hop = ''
		if self.next_hop:
			next_hop = ' next-hop %s' % self.next_hop 
		elif self.next_hop6:
			next_hop = ' next-hop %s' % self.next_hop6

		return "%s%s%s%s" % (str(self.nlri),next_hop,local_pref,communities)


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
	ID   = 0x00
	FLAG = 0x00

	# This should move within the classes and not be here
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
		# This should move within the classes and not be here
		if self.ID == 0x01: return "ORIGIN"
		if self.ID == 0x02: return "AS_PATH"
		if self.ID == 0x03: return "NEXT_HOP"
		if self.ID == 0x04: return "MULTI_EXIT_DISC"
		if self.ID == 0x05: return "LOCAL_PREFERENCE"
		if self.ID == 0x06: return "ATOMIC_AGGREGATE"
		if self.ID == 0x07: return "AGGREGATOR"
		if self.ID == 0x08: return "COMMUNITY"
		if self.ID == 0x0e: return "MP_REACH_NLRI"
		if self.ID == 0x0f: return "MP_UNREACH_NLRI"
		return 'UNKNOWN ATTRIBUTE (%s)' % hex(self.ID)

	def _attribute (self,value):
		flag = self.FLAG
		if flag & Flag.OPTIONAL and not value:
			return ''
		length = len(value)
		if length > 0xFF:
			flag &= Flag.EXTENDED_LENGTH
		if flag & Flag.EXTENDED_LENGTH:
			len_value = pack('!H',length)[0]
		else:
			len_value = chr(length)
		return "%s%s%s%s" % (chr(flag),chr(self.ID),len_value,value)

	def _segment (self,seg_type,values):
		if len(values)>255:
			return self._segment(values[:256]) + self._segment(values[256:])
		return "%s%s%s" % (chr(seg_type),chr(len(values)),''.join([v.pack() for v in values]))

	def __cmp__ (self,other):
		if type(self) == type(other):
			return cmp(self.value,other.value)
		return cmp(self.value,other)

# =================================================================== Attributes

def new_Attributes (data):
	attributes = Attributes()
	attributes.new(data)
	return attributes

class Attributes (dict):
	def has (self,k):
		return self.has_key(k)

	def add (self,attribute):
		if self.has(attribute.ID):
			if attribute.MULTIPLE:
				self[attribute.ID].append(attribute)
				return True
			return False
		else:
			if attribute.MULTIPLE:
				self[attribute.ID] = [attribute]
			else:
				self[attribute.ID] = attribute
			return True

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

		if code == Attribute.ORIGIN:
			self.add(new_Origin(data))
			return self.new(data[length:])

		if code == Attribute.AS_PATH:
			self.add(new_ASPath(data))
			return self.new(data[length:])

		if code == Attribute.NEXT_HOP:
			self.add(new_NextHop(data))
			return self.new(data[length:])

		if code == Attribute.MULTI_EXIT_DISC:
			self.add(new_MED(data))
			return self.new(data[length:])

		if code == Attribute.LOCAL_PREFERENCE:
			self.add(new_LocalPreference(data))
			return self.new(data[length:])

		if code == Attribute.ATOMIC_AGGREGATE:
			# ignore
			return self.new(data[length:])

		if code == Attribute.AGGREGATOR:
			# content is 6 bytes
			return self.new(data[length:])

		if code == Attribute.COMMUNITY:
			self.add(new_Communities(data))
			return self.new(data[length:])

		if code == Attribute.MP_UNREACH_NLRI:
			next_attributes = data[length:]
			data = data[:length]
			afi,safi = unpack('!HB',data[:3])
			offset = 3
			# XXX: See RFC 5549 for better support
			if not afi in (AFI.ipv4,AFI.ipv6) or safi != SAFI.unicast:
				print 'we only understand IPv4/IPv6 and should never have received this route (%s %s)' % (afi,safi)
				return self.new(next_attributes)
			data = data[offset:]
			while data:
				route = Update(new_NLRI(data,afi))
				data = data[len(route.nlri):]
				self.add(MPURNLRI(route))
				print 'removing MP route %s' % str(route)
			return self.new(next_attributes)

		if code == Attribute.MP_REACH_NLRI:
			next_attributes = data[length:]
			data = data[:length]
			afi,safi = unpack('!HB',data[:3])
			offset = 3
			if not afi in (AFI.ipv4,AFI.ipv6) or safi != SAFI.unicast:
				print 'we only understand IPv4/IPv6 and should never have received this route (%s %s)' % (afi,safi)
				return self.new(next_attributes)
			len_nh = ord(data[offset])
			offset += 1
			if afi == AFI.ipv4 and not len_nh != 4:
				# We are not following RFC 4760 Section 7 (deleting route and possibly tearing down the session)
				print 'bad IPv4 next-hop length (%d)' % len_nh
				return self(next_attributes)
			if afi == AFI.ipv6 and not len_nh in (16,32):
				# We are not following RFC 4760 Section 7 (deleting route and possibly tearing down the session)
				print 'bad IPv6 next-hop length (%d)' % len_nh
				return self(next_attributes)
			nh = data[offset:offset+len_nh]
			offset += len_nh
			if len_nh == 32:
				# we have a link-local address in the next-hop we ideally need to ignore
				if nh[0] == 0xfe: nh = nh[16:]
				elif nh[16] == 0xfe: nh = nh[:16]
				# We are not following RFC 4760 Section 7 (deleting route and possibly tearing down the session)
				else: self(next_attributes)
			nh = socket.inet_ntop(socket.AF_INET6 if len_nh >= 16 else socket.AF_INET,nh)
			nb_snpa = ord(data[offset])
			offset += 1
			snpas = []
			for i in range(nb_snpa):
				len_snpa = ord(offset)
				offset += 1
				snpas.append(data[offset:offset+len_snpa])
				offset += len_snpa
			data = data[offset:]
			while data:
				route = Update(new_NLRI(data,afi))
				route.next_hop6 = nh
				data = data[len(route.nlri):]
				self.add(MPRNLRI(route))
				print 'adding MP route %s' % str(route)
			return self.new(next_attributes)

		import warnings
		warnings.warn("Could not parse attribute %s" % str(code))
		return self.new(data[length:])

# =================================================================== Origin (1)

def new_Origin (data):
	return Origin(ord(data[0]))

class Origin (Attribute):
	ID = Attribute.ORIGIN
	FLAG = Flag.TRANSITIVE
	MULTIPLE = False

	IGP        = 0x00
	EGP        = 0x01
	INCOMPLETE = 0x02

	def pack (self):
		return self._attribute(chr(self.value))

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		if self.value == 0x00: return 'IGP'
		if self.value == 0x01: return 'EGP'
		if self.value == 0x02: return 'INCOMPLETE'
		return 'INVALID'


# =================================================================== ASPath (2)

def new_ASPath (data):
	stype = ord(data[0])
	slen = ord(data[1])
	sdata = data[2:2+(slen*2)]

	ASPS = ASPath(stype)
	for c in unpack('!'+('H'*slen),sdata):
		ASPS.add(c)
	return ASPS

class ASPath (Attribute):
	AS_SET      = 0x01
	AS_SEQUENCE = 0x02

	ID = Attribute.AS_PATH
	FLAG = Flag.TRANSITIVE
	MULTIPLE = False

	def __init__ (self,asptype,aspsegment = []):
		Attribute.__init__(self,(asptype,aspsegment))

	def add (self,community):
		self.value[1].append(community)

	def pack (self):
		return self._attribute(self._segment(self.value[0],self.value[1]))

	def __len__ (self):
		return 2 + (len(self.value[1])*2)

	def __str__ (self):
		if self.value[0] == 0x01: t = 'AS_SET'
		if self.value[0] == 0x02: t = 'AS_SEQUENCE'
		else: t = 'INVALID'

		if len(self) >  1: return '%s [ %s ]' % (t,' '.join([str(community) for community in self.value[1]]))
		if len(self) == 1: return '%s %s' % (t,str(self.value[1][0]))
		return t

# =================================================================== NextHop (3)
# XXX: WE STILL USE IP IN THE CODE


def new_NextHop (data):
	return NextHop(socket.inet_ntop(socket.AF_INET,data[:4]))

def to_NextHop (ip):
	return NextHop(ip)

class NextHop (Attribute):
	ID = Attribute.NEXT_HOP
	FLAG = Flag.TRANSITIVE
	MULTIPLE = False

	def __init__ (self,value):
		Attribute.__init__(self,IPv4(value))

	def pack (self):
		return self._attribute(self.value.pack())

	def __len__ (self):
		return len(self.value.pack())

	def __str__ (self):
		return str(self.value)

# =================================================================== MED (4)

def new_MED (data):
	return MED(unpack('!L',data[:4])[0])

class MED (Attribute):
	ID = Attribute.MULTI_EXIT_DISC  
	FLAG = Flag.TRANSITIVE
	MULTIPLE = False

	def pack (self):
		return pack('!L',self.value)

	def __len__ (self):
		return 4

	def __str__ (self):
		return str(self.value)

# =================================================================== Local Preference (5)

def new_LocalPreference (data):
	return LocalPreference(unpack('!L',data[:4])[0])

class LocalPreference (Attribute):
	ID = Attribute.LOCAL_PREFERENCE 
	FLAG = Flag.TRANSITIVE
	MULTIPLE = False

	def pack (self):
		message += self._attribute(pack('!L',self.value))

	def __len__ (self):
		return 4
	
	def __str__ (self):
		return str(self.value)

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
		Communities.add(Community(community))
	return communities

class Community (long):
	def pack (self):
		return pack('!L',self)

	def __str__ (self):
		return "%d:%d" % (self >> 16, self & 0xFFFF)

	def __len__ (self):
		return 4

class Communities (Attribute):
	ID = Attribute.COMMUNITY
	FLAG = Flag.TRANSITIVE|Flag.OPTIONAL
	MULTIPLE = False

	def __init__ (self,value=None):
		# Must be None as = param is only evaluated once
		Attribute.__init__(self,value if value else [])

	def add(self,data):
		return self.value.append(data)

	def pack (self):
		if len(self.value):
			return self._attribute(''.join([c.pack() for c in self.value])) 
		return ''

	# XXX: Check if this is right ........
	def __len__ (self):
		return 2 + len(self.values)*4


	def __str__ (self):
		l = len(self.value)
		if l > 1:
			return "[ %s ]" % " ".join(str(community) for community in self.value)
		if l == 1:
			return str(self.value[0])
		return ""

# =================================================================== MP NLRI (14)

class MPURNLRI (Attribute):
	FLAG = Flag.TRANSITIVE
	ID = Attribute.MP_UNREACH_NLRI  
	MULTIPLE = True

	def pack (self):
		return self._attribute(AFI(AFI.ipv6).pack() + SAFI(SAFI.unicast).pack() + self.value.nlri.pack())

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		return "MP Unreacheable NLRI"

# =================================================================== MP Unreacheable NLRI (15)

class MPRNLRI (Attribute):
	FLAG = Flag.TRANSITIVE
	ID = Attribute.MP_REACH_NLRI    
	MULTIPLE = True

	def __init__ (self,route):
		Attribute.__init__(self,route)

	def pack (self):
		next_hop = self.route.next_hop.pack() if self.next_hop else '\0'
		return self._attribute(
			AFI(AFI.ipv6).pack() + SAFI(SAFI.unicast).pack() + 
			chr(len(next_hop)) + next_hop + 
			chr(0) + self.route.nlri.pack()
		)

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		return "MP Reacheable NLRI"

# The past :)
#		message += self._attribute(Flag.TRANSITIVE,ORIGIN,Origin(Origin.IGP).pack())
#		message += self._attribute(Flag.TRANSITIVE,AS_PATH,'' if local_asn == peer_asn else self._segment(ASPath.AS_SEQUENCE,[local_asn]))
#		if local_asn == peer_asn:
#			message += self._attribute(Flag.TRANSITIVE,LOCAL_PREFERENCE,self.local_preference.pack())
#		message += self._attribute(Flag.TRANSITIVE|Flag.OPTIONAL,COMMUNITY,''.join([c.pack() for c in self.communities])) if self.communities else ''
#		if self.nlri.afi == AFI.ipv4:
#			message += self._attribute(Flag.TRANSITIVE,NEXT_HOP,self.next_hop.pack())
#		if self.nlri.afi == AFI.ipv6:
#			if mp_action == '-':
#				attr = AFI(AFI.ipv6).pack() + SAFI(SAFI.unicast).pack() + Prefix.pack(self)
#				message += self._attribute(Flag.TRANSITIVE,MP_UNREACH_NLRI,attr)
#			if mp_action == '+':
#				prefix = self.nlri.pack()
#				next_hop = self.next_hop.pack()
#				attr = AFI(AFI.ipv6).pack() + SAFI(SAFI.unicast).pack() + chr(len(next_hop)) + next_hop + chr(0) + prefix
#				message += self._attribute(Flag.TRANSITIVE,MP_REACH_NLRI,attr)
#		return message

