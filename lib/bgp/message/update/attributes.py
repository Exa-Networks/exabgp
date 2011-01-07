#!/usr/bin/env python
# encoding: utf-8
"""
set.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2010 Exa Networks. All rights reserved.
"""

from bgp.structure.address import AFI,SAFI
from bgp.structure.asn import AS_TRANS
from bgp.message.update.attribute import AttributeID

from bgp.message.update.attribute.origin      import Origin
from bgp.message.update.attribute.aspath      import ASPath,AS4Path
from bgp.message.update.attribute.localpref   import LocalPreference

# =================================================================== Attributes

class MultiAttributes (list):
	def __init__ (self,attribute):
		list.__init__(self)
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

	def _as_path (self,asn4,asp):
		message = ''
		# if the peer does not understand ASN4, we need to build a transitive AS4_PATH
		if not asn4:
			has_asn4 = False
			aspath = ASPath(False,asp.asptype)
			as4path = AS4Path(asp.asptype)
			for segment in asp.aspsegment:
				if segment.asn4():
					has_asn4 = True
					aspath.add(AS_TRANS)
					as4path.add(segment)
				else:
					aspath.add(segment)
			message += aspath.pack()
			if has_asn4:
				message += as4path.pack()
		else:
			message += ASPath(asn4,asp.asptype,asp.aspsegment).pack()
		return message

	def bgp_announce (self,asn4,local_asn,peer_asn):
		ibgp = (local_asn == peer_asn)
		# we do not store or send MED
		message = ''

		if AttributeID.ORIGIN in self:
			message += self[AttributeID.ORIGIN].pack()
		elif self.autocomplete:
			message += Origin(Origin.IGP).pack()

		if AttributeID.AS_PATH in self:
			asp = self[AttributeID.AS_PATH]
		elif self.autocomplete:
			if ibgp:
				asp = ASPath(asn4,ASPath.AS_SEQUENCE,[])
			else:
				asp = ASPath(asn4,ASPath.AS_SEQUENCE,[local_asn])
		message += self._as_path(asn4,asp)

		if AttributeID.NEXT_HOP in self:
			afi = self[AttributeID.NEXT_HOP].next_hop.afi
			safi = self[AttributeID.NEXT_HOP].next_hop.safi
			if afi == AFI.ipv4 and safi in [SAFI.unicast, SAFI.multicast]:
				message += self[AttributeID.NEXT_HOP].pack()

		if ibgp:
			if AttributeID.LOCAL_PREF in self:
				message += self[AttributeID.LOCAL_PREF].pack()
			else:
				message += LocalPreference(100).pack()

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

		local_pref = ''
		if self.has(AttributeID.LOCAL_PREF):
			l = self[AttributeID.LOCAL_PREF]
			local_pref = ' local_preference %s' % l

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

