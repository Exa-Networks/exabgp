# encoding: utf-8
"""
parse_l2vpn.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.current.core import Section

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
from exabgp.configuration.current.static.parser import name as named
from exabgp.configuration.current.static.parser import split
from exabgp.configuration.current.static.parser import watchdog
from exabgp.configuration.current.static.parser import withdraw

from exabgp.configuration.current.static.mpls import route_distinguisher

from exabgp.configuration.current.l2vpn.parser import vpls
from exabgp.configuration.current.l2vpn.parser import vpls_endpoint
from exabgp.configuration.current.l2vpn.parser import vpls_size
from exabgp.configuration.current.l2vpn.parser import vpls_offset
from exabgp.configuration.current.l2vpn.parser import vpls_base

# self.command = {
# 	'endpoint':            self.vpls_endpoint,
# 	'offset':              self.vpls_offset,
# 	'size':                self.vpls_size,
# 	'base':                self.vpls_base,
# 	'origin':              self.origin,
# 	'as-path':             self.aspath,
# 	'med':                 self.med,
# 	'next-hop':            self.next_hop,
# 	'local-preference':    self.local_preference,
# 	'originator-id':       self.originator_id,
# 	'cluster-list':        self.cluster_list,
# 	'rd':                  self.rd,
# 	'route-distinguisher': self.rd,
# 	'withdraw':            self.withdraw,
# 	'withdrawn':           self.withdraw,
# 	'name':                self.name,
# 	'community':           self.community,
# 	'extended-community':  self.extended_community,
# }


class ParseVPLS (Section):
	definition = [
		'endpoint <vpls endpoint id; integer>',
		'base <label base; integer>',
		'offset <block offet; interger>',
		'size <block size; integer>',

		'next-hop <ip>',
		'med <16 bits number>',
		'route-distinguisher|rd <ipv4>:<port>|<16bits number>:<32bits number>|<32bits number>:<16bits number>',
		'origin IGP|EGP|INCOMPLETE',
		'as-path [ <asn>.. ]',
		'local-preference <16 bits number>',
		'atomic-aggregate',
		'community <16 bits number>',
		'extended-community target:<16 bits number>:<ipv4 formated number>',
		'originator-id <ipv4>',
		'cluster-list <ipv4>',
		'label <15 bits number>',
		'attribute [ generic attribute format ]'
		'name <mnemonic>',
		'split /<mask>',
		'watchdog <watchdog-name>',
		'withdraw',
	]

	syntax = \
		'vpls {\n  %s\n}' % ' ;\n  '.join(definition)

	known = {
		'rd':                 route_distinguisher,
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
		'name':               named,
		'split':              split,
		'watchdog':           watchdog,
		'withdraw':           withdraw,
		'endpoint':           vpls_endpoint,
		'offset':             vpls_offset,
		'size':               vpls_size,
		'base':               vpls_base,
	}

	action = {
		'attribute':          'attribute-add',
		'next-hop':           'attribute-add',
		'origin':             'attribute-add',
		'med':                'attribute-add',
		'as-path':            'attribute-add',
		'local-preference':   'attribute-add',
		'atomic-aggregate':   'attribute-add',
		'aggregator':         'attribute-add',
		'originator-id':      'attribute-add',
		'cluster-list':       'attribute-add',
		'community':          'attribute-add',
		'extended-community': 'attribute-add',
		'name':               'attribute-add',
		'split':              'attribute-add',
		'watchdog':           'attribute-add',
		'withdraw':           'attribute-add',
		'rd':                 'nlri-set',
		'endpoint':           'nlri-set',
		'offset':             'nlri-set',
		'size':               'nlri-set',
		'base':               'nlri-set',
	}

	assign = {
		'rd':       'rd',
		'endpoint': 'endpoint',
		'offset':   'offset',
		'size':     'size',
		'base':     'base',
	}

	name = 'l2vpn/vpls'

	def __init__ (self, tokeniser, scope, error, logger):
		Section.__init__(self,tokeniser,scope,error,logger)

	def clear (self):
		pass

	def pre (self):
		self.scope.set(self.name,vpls(self.tokeniser.iterate))
		return True

	def post (self):
		if not self._check():
			return False
		# self.scope.to_context()
		route = self.scope.pop(self.name)
		if route:
			self.scope.extend('routes',route)
		return True

	def _check (self):
		nlri = self.scope.get(self.name).nlri

		if nlri.nexthop is None:
			return self.error.set('vpls next-hop missing')
		if nlri.endpoint is None:
			return self.error.set('vpls enpoint missing')
		if nlri.base is None:
			return self.error.set('vpls base missing')
		if nlri.offset is None:
			return self.error.set('vpls offset missing')
		if nlri.size is None:
			return self.error.set('vpls size missing')
		if nlri.base > (0xFFFFF - nlri.size):  # 20 bits, 3 bytes
			return self.error.set('vpls size inconsistancy')
		return True
