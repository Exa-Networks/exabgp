# encoding: utf-8
"""
inet/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

# This is a legacy file to handle 3.4.x like format


from exabgp.protocol.ip import IP
from exabgp.protocol.ip import NoNextHop

from exabgp.bgp.message import OUT

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri import INET
from exabgp.bgp.message.update.nlri import MPLS

from exabgp.bgp.message.update.attribute import Attribute

from exabgp.rib.change import Change

from exabgp.configuration.current.generic import Generic

from exabgp.configuration.current.static.parser import inet
from exabgp.configuration.current.static.parser import attribute
from exabgp.configuration.current.static.parser import next_hop
from exabgp.configuration.current.static.parser import origin
from exabgp.configuration.current.static.parser import med
from exabgp.configuration.current.static.parser import as_path
from exabgp.configuration.current.static.parser import local_preference
from exabgp.configuration.current.static.parser import atomic_aggregate
from exabgp.configuration.current.static.parser import aggregator
from exabgp.configuration.current.static.parser import originator_id
from exabgp.configuration.current.static.parser import cluster_list
from exabgp.configuration.current.static.parser import community
from exabgp.configuration.current.static.parser import extended_community
from exabgp.configuration.current.static.parser import aigp
from exabgp.configuration.current.static.parser import path_information
from exabgp.configuration.current.static.parser import name as named
from exabgp.configuration.current.static.parser import split
from exabgp.configuration.current.static.parser import watchdog
from exabgp.configuration.current.static.parser import withdraw


# Take an integer an created it networked packed representation for the right family (ipv4/ipv6)
def pack_int (afi, integer):
	return ''.join([chr((integer >> (offset * 8)) & 0xff) for offset in range(IP.length(afi)-1,-1,-1)])


class ParseRoute (Generic):
	# put next-hop first as it is a requirement atm
	definition = [
		'next-hop <ip>',
		'path-information <ipv4 formated number>',
		'route-distinguisher|rd <ipv4>:<port>|<16bits number>:<32bits number>|<32bits number>:<16bits number>',
		'origin IGP|EGP|INCOMPLETE',
		'as-path [ <asn>.. ]',
		'med <16 bits number>',
		'local-preference <16 bits number>',
		'atomic-aggregate',
		'community <16 bits number>',
		'extended-community target:<16 bits number>:<ipv4 formated number>',
		'originator-id <ipv4>',
		'cluster-list <ipv4>',
		'label <15 bits number>',
		'aggregator ( <asn16>:<ipv4> )',
		'aigp <40 bits number>',
		'attribute [ generic attribute format ]'
		'name <mnemonic>',
		'split /<mask>',
		'watchdog <watchdog-name>',
		'withdraw',
	]

	syntax = \
		'syntax:\n' \
		'route <ip>/<netmask> { ' \
		'\n   ' + ' ;\n   '.join(definition) + '\n}\n\n'

	# 'path-information':    self.path_information,
	# 'label':               self.label,
	# 'rd':                  self.rd,
	# 'route-distinguisher': self.rd,

	known = {
		'path-information':   path_information,
		'attribute':          attribute,
		'next-hop':           next_hop,
		'origin':             origin,
		'med':                med,
		'as-path':            as_path,
		'local-preference':   local_preference,
		'atomic-aggregate':   atomic_aggregate,
		'aggregator':         aggregator,
		'originator-id':      originator_id,
		'cluster-list':       cluster_list,
		'community':          community,
		'extended-community': extended_community,
		'aigp':               aigp,
		'name':               named,
		'split':              split,
		'watchdog':           watchdog,
		'withdraw':           withdraw,
	}

	add = [
		'attribute',
		'next-hop',
		'origin',
		'med',
		'as-path',
		'local-preference',
		'atomic-aggregate',
		'aggregator',
		'originator-id',
		'cluster-list',
		'community',
		'extended-community',
		'name',
		'split',
		'watchdog',
		'withdraw',
		'aigp',
	]

	nlri = [
		'path-info',  # The INET class does not have the hook for this to work yet
	]

	append = [
		'route',
	]

	name = 'route'

	def __init__ (self, tokeniser, scope, error, logger):
		Generic.__init__(self,tokeniser,scope,error,logger)

		self.default = {
			'next-hop': None,
		}

	def clear (self):
		self.default['next-hop'] = None

	def nexthop (self, nexthopself):
		self.default['next-hop'] = nexthopself

	def pre (self):
		self.scope.set(self.name,inet(self.tokeniser.iterate))
		return True

	def post (self):
		if not self._check():
			return False
		if not self._split():
			return False
		last = self.scope.pop_last(self.name)
		self.scope.append('routes',last)
		return True

	def _check (self):
		last = self.scope.last(self.name)
		if last.nlri.nexthop is NoNextHop \
			and last.nlri.afi == AFI.ipv4 \
			and last.nlri.safi in (SAFI.unicast,SAFI.multicast):
			return self.error.set(self.syntax)
		return True

	def _split (self):
		last = self.scope.last(self.name)

		if Attribute.CODE.INTERNAL_SPLIT not in last.attributes:
			return True

		# ignore if the request is for an aggregate, or the same size
		mask = last.nlri.mask
		cut = last.attributes[Attribute.CODE.INTERNAL_SPLIT]
		if mask >= cut:
			return True

		last = self.scope.pop_last(self.name)

		# calculate the number of IP in the /<size> of the new route
		increment = pow(2,(len(last.nlri.packed)*8) - cut)
		# how many new routes are we going to create from the initial one
		number = pow(2,cut - last.nlri.mask)

		# convert the IP into a integer/long
		ip = 0
		for c in last.nlri.packed:
			ip <<= 8
			ip += ord(c)

		afi = last.nlri.afi
		safi = last.nlri.safi

		# Really ugly
		klass = last.nlri.__class__
		if klass is INET:
			path_info = last.nlri.path_info
		elif klass is MPLS:
			path_info = None
			labels = last.nlri.labels
			rd = last.nlri.rd

		# packed and not pack() but does not matter atm, it is an IP not a NextHop
		nexthop = last.nlri.nexthop.packed

		last.nlri.mask = cut
		last.nlri = None

		# generate the new routes
		for _ in range(number):
			# update ip to the next route, this recalculate the "ip" field of the Inet class
			nlri = klass(afi,safi,pack_int(afi,ip),cut,nexthop,OUT.ANNOUNCE,path_info)
			if klass is MPLS:
				nlri.labels = labels
				nlri.rd = rd
			# next ip
			ip += increment
			self.scope.append(self.name,Change(nlri,last.attributes))

		return True
