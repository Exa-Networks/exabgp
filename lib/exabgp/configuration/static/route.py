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

from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.attribute import Attribute

from exabgp.rib.change import Change

from exabgp.configuration.core import Section

# from exabgp.configuration.static.parser import inet
from exabgp.configuration.static.parser import mpls
from exabgp.configuration.static.parser import attribute
from exabgp.configuration.static.parser import next_hop
from exabgp.configuration.static.parser import origin
from exabgp.configuration.static.parser import med
from exabgp.configuration.static.parser import as_path
from exabgp.configuration.static.parser import local_preference
from exabgp.configuration.static.parser import atomic_aggregate
from exabgp.configuration.static.parser import aggregator
from exabgp.configuration.static.parser import originator_id
from exabgp.configuration.static.parser import cluster_list
from exabgp.configuration.static.parser import community
from exabgp.configuration.static.parser import large_community
from exabgp.configuration.static.parser import extended_community
from exabgp.configuration.static.parser import aigp
from exabgp.configuration.static.parser import path_information
from exabgp.configuration.static.parser import name as named
from exabgp.configuration.static.parser import split
from exabgp.configuration.static.parser import watchdog
from exabgp.configuration.static.parser import withdraw
from exabgp.configuration.static.mpls import route_distinguisher
from exabgp.configuration.static.mpls import label


# Take an integer an created it networked packed representation for the right family (ipv4/ipv6)
def pack_int (afi, integer):
	return b''.join([chr((integer >> (offset * 8)) & 0xff) for offset in range(IP.length(afi)-1,-1,-1)])


class ParseStaticRoute (Section):
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
		'large-community <96 bits number>',
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
		'route <ip>/<netmask> { ' \
		'\n   ' + ' ;\n   '.join(definition) + '\n}'

	known = {
		'path-information':    path_information,
		'rd':                  route_distinguisher,
		'route-distinguisher': route_distinguisher,
		'label':               label,
		'attribute':           attribute,
		'next-hop':            next_hop,
		'origin':              origin,
		'med':                 med,
		'as-path':             as_path,
		'local-preference':    local_preference,
		'atomic-aggregate':    atomic_aggregate,
		'aggregator':          aggregator,
		'originator-id':       originator_id,
		'cluster-list':        cluster_list,
		'community':           community,
		'large-community':     large_community,
		'extended-community':  extended_community,
		'aigp':                aigp,
		'name':                named,
		'split':               split,
		'watchdog':            watchdog,
		'withdraw':            withdraw,
	}

	action = {
		'path-information':    'nlri-set',
		'rd':                  'nlri-set',
		'route-distinguisher': 'nlri-set',
		'label':               'nlri-set',
		'attribute':           'attribute-add',
		'next-hop':            'nexthop-and-attribute',
		'origin':              'attribute-add',
		'med':                 'attribute-add',
		'as-path':             'attribute-add',
		'local-preference':    'attribute-add',
		'atomic-aggregate':    'attribute-add',
		'aggregator':          'attribute-add',
		'originator-id':       'attribute-add',
		'cluster-list':        'attribute-add',
		'community':           'attribute-add',
		'large-community':     'attribute-add',
		'extended-community':  'attribute-add',
		'name':                'attribute-add',
		'split':               'attribute-add',
		'watchdog':            'attribute-add',
		'withdraw':            'attribute-add',
		'aigp':                'attribute-add',
	}

	assign = {
		'path-information':    'path_info',
		'rd':                  'rd',
		'route-distinguisher': 'rd',
		'label':               'labels',
	}

	name = 'static/route'

	def __init__ (self, tokeniser, scope, error, logger):
		Section.__init__(self,tokeniser,scope,error,logger)

	def clear (self):
		return True

	def pre (self):
		self.scope.set(self.name,mpls(self.tokeniser.iterate))
		# self.scope.set(self.name,inet(self.tokeniser.iterate))
		return True

	def post (self):
		# self._family()
		self._split()
		# self.scope.to_context()
		routes = self.scope.pop(self.name)
		if routes:
			for route in routes:
				# if route.nlri.has_rd():
				if route.nlri.rd is not RouteDistinguisher.NORD:
					route.nlri.safi = SAFI(SAFI.mpls_vpn)
				# elif route.nlri.has_label():
				elif route.nlri.labels is not Labels.NOLABEL:
					route.nlri.safi = SAFI(SAFI.nlri_mpls)

			self.scope.extend('routes',routes)
		return True

	# def _family (self):
	# 	last = self.scope.get(self.name)
	# 	if last.nlri.labels and not last.nlri.safi.has_label():
	# 		last.nlri.safi = SAFI(SAFI.nlri_mpls)

	def _check (self):
		if not self.check(self.scope.get(self.name)):
			return self.error.set(self.syntax)
		return True

	@staticmethod
	def check (change):
		if change.nlri.nexthop is NoNextHop \
			and change.nlri.action == OUT.ANNOUNCE \
			and change.nlri.afi == AFI.ipv4 \
			and change.nlri.safi in (SAFI.unicast,SAFI.multicast):
			return False
		return True

	@staticmethod
	def split (last):
		if Attribute.CODE.INTERNAL_SPLIT not in last.attributes:
			yield last
			return

		# ignore if the request is for an aggregate, or the same size
		mask = last.nlri.cidr.mask
		cut = last.attributes[Attribute.CODE.INTERNAL_SPLIT]
		if mask >= cut:
			yield last
			return

		# calculate the number of IP in the /<size> of the new route
		increment = pow(2,last.nlri.afi.mask() - cut)
		# how many new routes are we going to create from the initial one
		number = pow(2,cut - last.nlri.cidr.mask)

		# convert the IP into a integer/long
		ip = 0
		for c in last.nlri.cidr.ton():
			ip <<= 8
			ip += ord(c)

		afi = last.nlri.afi
		safi = last.nlri.safi

		# Really ugly
		klass = last.nlri.__class__
		path_info = last.nlri.path_info
		nexthop = last.nlri.nexthop
		if klass.has_label():
			labels = last.nlri.labels
		if klass.has_rd():
			rd = last.nlri.rd

		# XXX: Looks weird to set and then set to None, check
		last.nlri.cidr.mask = cut
		last.nlri = None

		# generate the new routes
		for _ in range(number):
			# update ip to the next route, this recalculate the "ip" field of the Inet class
			nlri = klass(afi,safi,OUT.ANNOUNCE)
			nlri.cidr = CIDR(pack_int(afi,ip),cut)
			nlri.nexthop = nexthop  # nexthop can be NextHopSelf
			nlri.path_info = path_info
			# Really ugly
			if klass.has_label():
				nlri.labels = labels
			if klass.has_rd():
				nlri.rd = rd
			# next ip
			ip += increment
			yield Change(nlri,last.attributes)

	def _split (self):
		for splat in self.split(self.scope.pop(self.name)):
			self.scope.append(self.name,splat)
