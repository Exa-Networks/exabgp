# encoding: utf-8
"""
parse_l2vpn.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import SAFI
from exabgp.bgp.message.update.attribute import Attributes
from exabgp.rib.change import Change
from exabgp.bgp.message.update.nlri import VPLS

from exabgp.configuration.current.route import ParseRoute


class ParseL2VPN (ParseRoute):
	syntax = \
		'syntax:\n' \
		'  l2vpn {\n' \
		'    vpls site_name {\n' \
		'       endpoint <vpls endpoint id; integer>\n' \
		'       base <label base; integer>\n' \
		'       offset <block offet; interger>\n' \
		'       size <block size; integer>\n' \
		'       route-distinguisher|rd 255.255.255.255:65535|65535:65536|65536:65535\n' \
		'       next-hop 192.0.1.254;\n' \
		'       origin IGP|EGP|INCOMPLETE;\n' \
		'       as-path [ as as as as] ;\n' \
		'       med 100;\n' \
		'       local-preference 100;\n' \
		'       community [ 65000 65001 65002 ];\n' \
		'       extended-community [ target:1234:5.6.7.8 target:1.2.3.4:5678 origin:1234:5.6.7.8 origin:1.2.3.4:5678 0x0002FDE800000001 l2info:19:0:1500:111 ]\n' \
		'       originator-id 10.0.0.10;\n' \
		'       cluster-list [ 10.10.0.1 10.10.0.2 ];\n' \
		'       withdraw\n' \
		'       name what-you-want-to-remember-about-the-route\n' \
		'    }\n' \
		'  }\n'

	_str_vpls_bad_size = "you tried to configure an invalid l2vpn vpls block-size"
	_str_vpls_bad_offset = "you tried to configure an invalid l2vpn vpls block-offset"
	_str_vpls_bad_label = "you tried to configure an invalid l2vpn vpls label"
	_str_vpls_bad_enpoint = "you tried to configure an invalid l2vpn vpls endpoint"

	def __init__ (self, scope, error, logger):
		self.scope = scope
		self.error = error
		self.logger = logger

		self.command = {
			'endpoint':            self.vpls_endpoint,
			'offset':              self.vpls_offset,
			'size':                self.vpls_size,
			'base':                self.vpls_base,
			'origin':              self.origin,
			'as-path':             self.aspath,
			'med':                 self.med,
			'next-hop':            self.next_hop,
			'local-preference':    self.local_preference,
			'originator-id':       self.originator_id,
			'cluster-list':        self.cluster_list,
			'rd':                  self.rd,
			'route-distinguisher': self.rd,
			'withdraw':            self.withdraw,
			'withdrawn':           self.withdraw,
			'name':                self.name,
			'community':           self.community,
			'extended-community':  self.extended_community,
		}

	def clear (self):
		pass

	def vpls_endpoint (self, name, command, token):
		number = int(token.pop(0))
		if number < 0 or number > 0xFFFF:
			return self.error.set(self._str_vpls_bad_enpoint)

		vpls = self.scope.content[-1]['announce'][-1].nlri
		vpls.ve = number
		return True

	def vpls_size (self, name, command, token):
		number = int(token.pop(0))
		if number < 0 or number > 0xFFFF:
			return self.error.set(self._str_vpls_bad_size)

		vpls = self.scope.content[-1]['announce'][-1].nlri
		vpls.size = number
		return True

	def vpls_offset (self, name, command, token):
		number = int(token.pop(0))
		if number < 0 or number > 0xFFFF:
			return self.error.set(self._str_vpls_bad_offset)

		vpls = self.scope.content[-1]['announce'][-1].nlri
		vpls.offset = number
		return True

	def vpls_base (self, name, command, token):
		number = int(token.pop(0))
		if number < 0 or number > 0xFFFF:
			return self.error.set(self._str_vpls_bad_label)

		vpls = self.scope.content[-1]['announce'][-1].nlri
		vpls.base = number
		return True

	def vpls (self, name, command, tokens):
		# TODO: actual length?(like rd+lb+bo+ve+bs+rd; 14 or so)
		if len(tokens) < 10:
			return self.error.set('not enough parameter to make a vpls')

		if not self.insert_vpls(name,command,tokens):
			return False

		while len(tokens):
			command = tokens.pop(0)
			if len(tokens) < 1:
				return self.error.set('not enought tokens to make a vpls')

			if command not in self.command:
				return self.error.set('unknown vpls command %s' % command)
			elif command in ('rd','route-distinguisher'):
				if not self.command[command](name,command,tokens,SAFI.vpls):
					return False
			elif not self.command[command](name,command,tokens):
				return False

		if not self.check_vpls(self):
			return False
		return True

	def insert_vpls (self, name, command, tokens=None):
		try:
			attributes = Attributes()
			change = Change(VPLS(None,None,None,None,None),attributes)
		except ValueError:
			return self.error.set(self.syntax)

		if 'announce' not in self.scope.content[-1]:
			self.scope.content[-1]['announce'] = []

		self.scope.content[-1]['announce'].append(change)
		return True

	def check_vpls (self,configuration):
		nlri = self.scope.content[-1]['announce'][-1].nlri

		if nlri.ve is None:
			return self.error.set(self._str_vpls_bad_enpoint)

		if nlri.base is None:
			return self.error.set(self._str_vpls_bad_label)

		if nlri.offset is None:
			return self.error.set(self._str_vpls_bad_offset)

		if nlri.size is None:
			return self.error.set(self._str_vpls_bad_size)

		if nlri.base > (0xFFFFF - nlri.size):  # 20 bits, 3 bytes
			return self.error.set(self._str_vpls_bad_label)

		return True
