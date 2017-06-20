# encoding: utf-8
"""
announce/ipv4.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# This is a legacy file to handle 3.4.x like format

from exabgp.util import character
from exabgp.util import ordinal
from exabgp.util import concat_bytes_i


from exabgp.protocol.ip import IP
from exabgp.protocol.ip import NoNextHop

from exabgp.rib.change import Change

from exabgp.bgp.message import OUT

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri import INET
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute import Attributes

from exabgp.configuration.core import Section

from exabgp.configuration.static.parser import prefix
from exabgp.configuration.static.parser import inet
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
from exabgp.configuration.static.parser import name as named
from exabgp.configuration.static.parser import split
from exabgp.configuration.static.parser import watchdog
from exabgp.configuration.static.parser import withdraw
from exabgp.configuration.static.mpls import label


# Take an integer an created it networked packed representation for the right family (ipv4/ipv6)
def pack_int (afi, integer):
	return concat_bytes_i(character((integer >> (offset * 8)) & 0xff) for offset in range(IP.length(afi)-1,-1,-1))


class ParseIP (Section):
	# put next-hop first as it is a requirement atm
	definition = [
		'next-hop <ip>',
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
		'bgp-prefix-sid [ 32 bits number> ] | [ <32 bits number>, [ ( <24 bits number>,<24 bits number> ) ]]',
		'aggregator ( <asn16>:<ipv4> )',
		'aigp <40 bits number>',
		'attribute [ generic attribute format ]'
		'name <mnemonic>',
		'split /<mask>',
		'watchdog <watchdog-name>',
		'withdraw',
	]

	syntax = \
		'<safi> <ip>/<netmask> { ' \
		'\n   ' + ' ;\n   '.join(definition) + '\n}'

	known = {
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
	}

	name = 'ip'
	afi = None

	def __init__ (self, tokeniser, scope, error, logger):
		Section.__init__(self,tokeniser,scope,error,logger)

	def clear (self):
		return True

	def pre (self):
		# self.scope.set(self.name,inet(self.tokeniser.iterate))
		return True

	def post (self):
		self._split()
		routes = self.scope.pop(self.name)
		if routes:
			self.scope.extend('routes',routes)
		return True

	def _check (self):
		if not self.check(self.scope.get(self.name),self.afi):
			return self.error.set(self.syntax)
		return True

	@staticmethod
	def check (change,afi):
		if change.nlri.nexthop is NoNextHop \
			and change.nlri.action == OUT.ANNOUNCE \
			and change.nlri.afi == afi \
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
			ip += ordinal(c)

		afi = last.nlri.afi
		safi = last.nlri.safi

		# Really ugly
		klass = last.nlri.__class__
		path_info = last.nlri.path_info
		nexthop = last.nlri.nexthop

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
			# next ip
			ip += increment
			yield Change(nlri,last.attributes)

	def _split (self):
		for route in self.scope.pop(self.name,[]):
			for splat in self.split(route):
				self.scope.append(self.name,splat)


def ip (tokeniser,afi,safi):
	ipmask = prefix(tokeniser)

	nlri = INET(afi,safi,OUT.ANNOUNCE)
	nlri.cidr = CIDR(ipmask.pack(),ipmask.mask)

	change = Change(
		nlri,
		Attributes()
	)

	while True:
		command = tokeniser()

		if not command:
			break

		action = ParseIP.action.get(command,'')

		if action == 'attribute-add':
			change.attributes.add(ParseIP.known[command](tokeniser))
		elif action == 'nlri-set':
			change.nlri.assign(ParseIP.assign[command],ParseIP.known[command](tokeniser))
		elif action == 'nexthop-and-attribute':
			nexthop,attribute = ParseIP.known[command](tokeniser)
			change.nlri.nexthop = nexthop
			change.attributes.add(attribute)
		else:
			raise ValueError('route: unknown command "%s"' % command)

	return [change]


class ParseIPv4 (ParseIP):
	name = 'ipv4'
	afi = AFI.ipv4


@ParseIPv4.register('unicast','extend-name',True)
def unicast_v4 (tokeniser):
	return ip(tokeniser,AFI.ipv4,SAFI.unicast)


@ParseIPv4.register('multicast','extend-name',True)
def multicast_v4 (tokeniser):
	return ip(tokeniser,AFI.ipv4,SAFI.multicast)


class ParseIPv6 (ParseIP):
	name = 'ipv6'
	afi = AFI.ipv6


@ParseIPv6.register('unicast','extend-name',True)
def unicast_v6 (tokeniser):
	return ip(tokeniser,AFI.ipv6,SAFI.unicast)


@ParseIPv6.register('multicast','extend-name',True)
def multicast_v6 (tokeniser):
	return ip(tokeniser,AFI.ipv6,SAFI.multicast)
