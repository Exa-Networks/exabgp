# encoding: utf-8
"""
parse_l2vpn.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.current.generic import Generic

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


class ParseVPLS (Generic):
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
		'syntax:\n' \
		'vpls { ' \
		'\n   ' + ' ;\n   '.join(definition) + '\n}\n\n'

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
	]

	nlri = [
		'rd',
		'endpoint',
		'offset',
		'size',
		'base',
	]

	append = [
		'vpls',
	]

	name = 'vpls'

	def __init__ (self, tokeniser, scope, error, logger):
		Generic.__init__(self,tokeniser,scope,error,logger)

	def clear (self):
		pass

	def pre (self):
		self.scope.set(self.name,vpls(self.tokeniser.iterate))
		return True

	def post (self):
		if not self._check():
			return False
		last = self.scope.pop_last(self.name)
		self.scope.append('routes',last)
		return True

	def _check (self):
		nlri = self.scope.last(self.name).nlri

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

	# def vpls (self, name, command, tokens):
	# 	# TODO: actual length?(like rd+lb+bo+ve+bs+rd; 14 or so)
	# 	if len(tokens) < 10:
	# 		return self.error.set('not enough parameter to make a vpls')
	#
	# 	if not self.insert_vpls(name,command,tokens):
	# 		return False
	#
	# 	while len(tokens):
	# 		command = tokens.pop(0)
	# 		if len(tokens) < 1:
	# 			return self.error.set('not enought tokens to make a vpls')
	#
	# 		if command not in self.command:
	# 			return self.error.set('unknown vpls command %s' % command)
	# 		elif command in ('rd','route-distinguisher'):
	# 			if not self.command[command](name,command,tokens,SAFI.vpls):
	# 				return False
	# 		elif not self.command[command](name,command,tokens):
	# 			return False
	#
	# 	if not self.check_vpls(self):
	# 		return False
	# 	return True
	#
	# def insert_vpls (self, name, command, tokens=None):
	# 	try:
	# 		attributes = Attributes()
	# 		change = Change(VPLS(None,None,None,None,None),attributes)
	# 	except ValueError:
	# 		return self.error.set(self.syntax)
	#
	# 	if 'announce' not in self.scope.content[-1]:
	# 		self.scope.content[-1]['announce'] = []
	#
	# 	self.scope.content[-1]['announce'].append(change)
	# 	return True
