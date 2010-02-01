#!/usr/bin/env python
# encoding: utf-8
"""
set.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2010 Exa Networks. All rights reserved.
"""

from bgp.message.update.attribute import AttributeID

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

# =================================================================== Attributes

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
		return 'MultiAttibutes(%s)' % ' '.join(str(_) for _ in self)

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

	def bgp_announce (self,local_asn,peer_asn):
		ibgp = local_asn == peer_asn
		# we do not store or send MED
		message = ''

		attributes = [self[a].ID for a in self]

		if AttributeID.ORIGIN in self:
			message += self[AttributeID.ORIGIN].pack()
		elif self.autocomplete:
			message += Origin(Origin.IGP).pack()

		if AttributeID.AS_PATH in self:
			message += self[AttributeID.AS_PATH].pack()
		elif self.autocomplete:
			if local_asn == peer_asn:
				message += ASPath(ASPath.AS_SEQUENCE,[]).pack()
			else:
				message += ASPath(ASPath.AS_SEQUENCE,[local_asn]).pack()

		if AttributeID.NEXT_HOP in self:
			afi = self[AttributeID.NEXT_HOP].next_hop.afi
			safi = self[AttributeID.NEXT_HOP].next_hop.safi
			if afi == AFI.ipv4 and safi in [SAFI.unicast, SAFI.multicast]:
				message += self[AttributeID.NEXT_HOP].pack()

		if AttributeID.LOCAL_PREF in self:
			if local_asn == peer_asn:
				message += self[AttributeID.LOCAL_PREF].pack()

		if AttributeID.MED in self:
			if local_asn != peer_asn:
				message += self[AttributeID.MED].pack()

		for attribute in [AttributeID.COMMUNITY,AttributeID.EXTENDED_COMMUNITY]:
			if attribute in self:
				message += self[attribute].pack()

		return message

	def __str__ (self):
		next_hop = ''
		if self.has(AttributeID.NEXT_HOP):
			next_hop = ' next-hop %s' % str(self[AttributeID.NEXT_HOP]).lower()

		origin = ''
		if self.has(AttributeID.ORIGIN):
			origin = ' origin %s' % str(self[AttributeID.ORIGIN]).lower()

		aspath = ''
		if self.has(AttributeID.AS_PATH):
			aspath = ' %s' % str(self[AttributeID.AS_PATH]).lower().replace('_','-')

		local_pref= ''
		if self.has(AttributeID.LOCAL_PREF):
			l = self[AttributeID.LOCAL_PREF]
			local_pref= ' local_preference %s' % l

		med = ''
		if self.has(AttributeID.MED):
			m = self[AttributeID.MED]
			med = ' med %s' % m

		communities = ''
		if self.has(AttributeID.COMMUNITY):
			communities = ' community %s' % str(self[AttributeID.COMMUNITY])

		ecommunities = ''
		if self.has(AttributeID.EXTENDED_COMMUNITY):
			ecommunities = ' extended community %s' % str(self[AttributeID.EXTENDED_COMMUNITY])

		mpr = ''
		if self.has(AttributeID.MP_REACH_NLRI):
			mpr = ' mp_reach_nlri %s' % str(self[AttributeID.MP_REACH_NLRI])

		return "%s%s%s%s%s%s%s%s" % (next_hop,origin,aspath,local_pref,med,communities,ecommunities,mpr)

