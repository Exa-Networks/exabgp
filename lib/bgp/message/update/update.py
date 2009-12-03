#!/usr/bin/env python
# encoding: utf-8
"""
update.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.utils import *



from bgp.utils import *
from bgp.message.inet         import AFI, SAFI, to_NLRI, new_NLRI, NLRI, to_IP, IP
from bgp.message.parent       import Message,prefix,defix

from bgp.message.update.attribute.origin      import *	# 01
from bgp.message.update.attribute.aspath      import *	# 02
from bgp.message.update.attribute.nexthop     import *	# 03
from bgp.message.update.attribute.med         import * 	# 04
from bgp.message.update.attribute.localpref   import *	# 05
from bgp.message.update.attribute.aggregate   import *	# 06
from bgp.message.update.attribute.aggregator  import *	# 07
from bgp.message.update.attribute.communities import *	# 08
# 09
# 10 - 0A
# 11 - 0B
# 12 - 0C
# 13 - 0D
from bgp.message.update.attribute.mprnlri     import *	# 14 - 0E
from bgp.message.update.attribute.mpurnlri    import *	# 15 - 0F

# =================================================================== List of NLRI

class NLRIS (list):
	def __str__ (self):
		return "NLRIS %s" % str([str(nlri) for nlri in self])

# =================================================================== Update

def new_Update (data):
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

		remove = NLRIS()
		while withdrawn:
			nlri = new_NLRI(withdrawn)
			withdrawn = withdrawn[len(nlri):]
			remove.append(Update(nlri,'-'))

		attributes = new_Attributes(attribute)

		announce = NLRIS()
		while announced:
			nlri = new_NLRI(announced)
			announced = announced[len(nlri):]
			announce.append(nlri)

		return Update(remove,announce,attributes)

def to_Update (withdraw,nlri,attributes=None):
	return Update(withdraw,nlri,attributes)

class Update (Message):
	TYPE = chr(0x02)

	def __init__ (self,withdraw,nlri,attributes):
		self.nlri = nlri

		self.withdraw = withdraw
		if attributes == None:
			self.attributes = Attributes()
		else:
			self.attributes = attributes

#	def get_next_hop (self):
#		return self.attributes.get(Attribute.NEXT_HOP,None)
#	def set_next_hop (self,ip):
#		self.attributes[Attribute.NEXT_HOP] = ip
#	next_hop = property(get_next_hop,set_next_hop)

	def pack_attributes (self,local_asn,peer_asn):
		ibgp = local_asn == peer_asn
		# we do not store or send MED
		message = ''

		attributes = [self.attributes[a].ID for a in self.attributes]

		if Attribute.ORIGIN in attributes:
			message += self.attributes[Attribute.ORIGIN].pack()
		elif self.attributes.autocomplete:
			message += Origin(Origin.IGP).pack()

		if Attribute.AS_PATH in attributes:
			message += self.attributes[Attribute.AS_PATH].pack()
		elif self.attributes.autocomplete:
			if local_asn == peer_asn:
				message += ASPath(ASPath.AS_SEQUENCE,[]).pack()
			else:
				message += ASPath(ASPath.AS_SEQUENCE,[local_asn]).pack()

		if Attribute.NEXT_HOP in attributes:
			message += self.attributes[Attribute.NEXT_HOP].pack()
		elif self.attributes.autocomplete:
			message += to_NextHop('0.0.0.0').pack()

		if Attribute.LOCAL_PREFERENCE in attributes:
			if local_asn == peer_asn:
				message += self.attributes[Attribute.LOCAL_PREFERENCE].pack()

		if Attribute.MULTI_EXIT_DISC in attributes:
			if local_asn != peer_asn:
				message += self.attributes[Attribute.MULTI_EXIT_DISC].pack()

		for attribute in [Communities.ID,MPURNLRI.ID,MPRNLRI.ID]:
			if  self.attributes.has(attribute):
				message += self.attributes[attribute].pack()

		return message

	def announce (self,local_asn,remote_asn):
		attributes = self.pack_attributes(local_asn,remote_asn)
		nlri = ''.join([nlri.pack() for nlri in self.nlri])
		return self._message(prefix('') + prefix(attributes) + nlri)

	def withdraw (self,local_asn=None,remote_asn=None):
		withdraw = ''.join([withdraw.packedip() for withdraw in self.withdraw])
		attributes = self.pack_attributes(local_asn,remote_asn)
		nlri = ''.join([nlri.pack() for nlri in self.nlri])
		return self._message(prefix(withdraw) + prefix(''))

	def update (self,local_asn,remote_asn):
		withdraw = ''.join([withdraw.packedip() for withdraw in self.withdraw])
		attributes = self.pack_attributes(local_asn,remote_asn)
		nlri = ''.join([nlri.pack() for nlri in self.nlri])
		return self._message(prefix(withdraw) + prefix(attributes) + nlri)

	def added (self):
		routes = NLRIS()
		for nlri in self.nlri:
			r = Route(nlri)
			r.attributes = self.attributes
			routes.append(r)
		return routes

	def removed (self):
		nlris = NLRIS()
		for nlri in self.withdraw:
			nlris.append(nlri)
		return nlris

# =================================================================== Route

def to_Route (ip,netmask):
	return Route(to_NLRI(ip,netmask))

def new_Route (data,afi):
	nlri = new_NLRI(data,afi)
	return Route(nlri)

class Route (object):
	def __init__ (self,nlri):
		self.nlri = nlri
		self.attributes = Attributes()

	def _set_next_hop (self,nh):
		self._next_hop = to_IP(nh)
	def _get_next_hop (self):
		return self._next_hop
	next_hop = property(_get_next_hop,_set_next_hop)

	def announce (self,local_asn,remote_asn):
		attributes = Attributes(self.attributes.copy())
		if self.nlri.afi == AFI.ipv4:
			attributes[Attribute.NEXT_HOP] = to_NextHop(self.next_hop.ip())
			return Update(NLRIS(),NLRIS([self.nlri]),attributes).announce(local_asn,remote_asn)
		if self.nlri.afi == AFI.ipv6:
			attributes[Attribute.NEXT_HOP] = to_NextHop('0.0.0.0')
			attributes[Attribute.MP_REACH_NLRI] = MPRNLRI(AFI(self.nlri.afi),SAFI(self.nlri.safi),self)
			return Update(NLRIS(),NLRIS(),attributes).announce(local_asn,remote_asn)

	def update (self,local_asn,remote_asn):
		attributes = Attributes(self.attributes.copy())
		if self.nlri.afi == AFI.ipv4:
			attributes[Attribute.NEXT_HOP] = to_NextHop(self.next_hop)
		return Update(NLRIS(),NLRIS([self.nlri]),attributes).update(local_asn,remote_asn)

	def __str__ (self):
		origin = ''
		if self.attributes.has(Attribute.ORIGIN):
			origin = ' origin %s' % str(self.attributes[Attribute.ORIGIN]).lower()

		aspath = ''
		if self.attributes.has(Attribute.AS_PATH):
			aspath = ' %s' % str(self.attributes[Attribute.AS_PATH]).lower().replace('_','-')

		local_pref= ''
		if self.attributes.has(Attribute.LOCAL_PREFERENCE):
			l = self.attributes[Attribute.LOCAL_PREFERENCE]
			local_pref= ' local_preference %s' % l

		if self.attributes.has(Attribute.MULTI_EXIT_DISC):
			m = self.attributes[Attribute.MULTI_EXIT_DISC]
			local_pref= ' med %s' % m

		communities = ''
		if self.attributes.has(Attribute.COMMUNITY):
			communities = ' community %s' % str(self.attributes[Attribute.COMMUNITY])

		next_hop = ''
		if self.attributes.has(Attribute.NEXT_HOP):
			next_hop = ' next-hop %s' % str(self.attributes[Attribute.NEXT_HOP])
		elif self.next_hop:
			next_hop = ' next-hop %s' % str(self.next_hop)

		return "%s%s%s%s%s%s" % (self.nlri,next_hop,origin,aspath,local_pref,communities)

# =================================================================== Attributes

def new_Attributes (data):
	attributes = Attributes()
	attributes.new(data)
	return attributes

class MultiAttributes (list):
	def __init__ (self,attribute):
		self.ID = attribute.ID
		self.FLAG = attribute.FLAG
		self.MULTIPLE = True
		self.append(attribute)

	def pack (self):
		r = []
		for attribute in self:
			r.append(attribute.pack())
		return ''.join(r)

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		return "MultiAttribute"

class Attributes (dict):
	autocomplete = True
	
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
				self[attribute.ID] = MultiAttributes(attribute)
			else:
				self[attribute.ID] = attribute
			return True

	def new (self,data):
		try:
			return self._new(data)
		except IndexError:
			raise
			raise Notify(3,2,data)

	def _new (self,data):
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
			self.add(new_NextHop(data[:4]))
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
				route = new_NLRI(data,afi)
				data = data[len(route.nlri):]
				self.add(MPURNLRI(AFI(afi),SAFI(safi),route))
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
				return self.new(next_attributes)
			if afi == AFI.ipv6 and not len_nh in (16,32):
				# We are not following RFC 4760 Section 7 (deleting route and possibly tearing down the session)
				print 'bad IPv6 next-hop length (%d)' % len_nh
				return self.new(next_attributes)
			nh = data[offset:offset+len_nh]
			offset += len_nh
			if len_nh == 32:
				# we have a link-local address in the next-hop we ideally need to ignore
				if nh[0] == 0xfe: nh = nh[16:]
				elif nh[16] == 0xfe: nh = nh[:16]
				# We are not following RFC 4760 Section 7 (deleting route and possibly tearing down the session)
				else: self(next_attributes)
			if len_nh >= 16: nh = socket.inet_ntop(socket.AF_INET6,nh)
			else: nh = socket.inet_ntop(socket.AF_INET,nh)
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
				route = new_Route(data,afi)
				route.next_hop = nh
				data = data[len(route.nlri):]
				self.add(MPRNLRI(AFI(afi),SAFI(safi),route))
				print 'adding MP route %s' % str(route)
			return self.new(next_attributes)

		import warnings
		warnings.warn("Could not parse attribute %s" % str(code))
		return self.new(data[length:])

# =================================================================== End-Of-Record

class Empty (object):
	def pack (self):
		return ''
	def __len__ (self):
		return 0

class EmptyRoute (Empty):
	nlri = Empty()

class EOR (object):
	def __init__ (self):
		self._announced = []

	def eors (self,families):
		self._announced = []
		r = ''
		for afi,safi in families:
			if safi != SAFI.unicast:
				continue
			if afi == AFI.ipv4:
				r += self.ipv4()
			else:
				r += self.mp(afi,safi)
			self._announced.append((afi,safi))
		return r

	def ipv4 (self):
		#attributes = EORAttributes()
		attributes = Attributes()
		attributes.autocomplete = False
		return Update([],[],attributes).announce(0,0)

	def mp (self,afi,safi):
		attributes = Attributes()
		attributes.autocomplete = False
		attributes.add(MPURNLRI(afi,safi,EmptyRoute()))
		return Update([],[],attributes).announce(0,0)

	def announced (self):
		return self._announced

