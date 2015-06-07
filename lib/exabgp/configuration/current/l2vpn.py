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

	def __init__ (self, error):
		self.error = error

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

	def vpls_endpoint (self, scope, command, token):
		number = int(token.pop(0))
		if number < 0 or number > 0xFFFF:
			return self.error.set(self._str_vpls_bad_enpoint)

		vpls = scope[-1]['announce'][-1].nlri
		vpls.ve = number
		return True

	def vpls_size (self, scope, command, token):
		number = int(token.pop(0))
		if number < 0 or number > 0xFFFF:
			return self.error.set(self._str_vpls_bad_size)

		vpls = scope[-1]['announce'][-1].nlri
		vpls.size = number
		return True

	def vpls_offset (self, scope, command, token):
		number = int(token.pop(0))
		if number < 0 or number > 0xFFFF:
			return self.error.set(self._str_vpls_bad_offset)

		vpls = scope[-1]['announce'][-1].nlri
		vpls.offset = number
		return True

	def vpls_base (self, scope, command, token):
		number = int(token.pop(0))
		if number < 0 or number > 0xFFFF:
			return self.error.set(self._str_vpls_bad_label)

		vpls = scope[-1]['announce'][-1].nlri
		vpls.base = number
		return True

	def vpls (self, scope, command, tokens):
		# TODO: actual length?(like rd+lb+bo+ve+bs+rd; 14 or so)
		if len(tokens) < 10:
			return False

		if not self.insert_vpls(scope,command,tokens):
			return False

		while len(tokens):
			command = tokens.pop(0)
			if len(tokens) < 1:
				return False
			if command in self.command:
				if command in ('rd','route-distinguisher'):
					if self.command[command](scope,command,tokens,SAFI.vpls):
						continue
				else:
					if self.command[command](scope,command,tokens):
						continue
			else:
				return False
			return False

		if not self.check_vpls(scope,self):
			return False
		return True

	def insert_vpls (self, scope, command, tokens=None):
		try:
			attributes = Attributes()
			change = Change(VPLS(None,None,None,None,None),attributes)
		except ValueError:
			return self.error.set(self.syntax)

		if 'announce' not in scope[-1]:
			scope[-1]['announce'] = []

		scope[-1]['announce'].append(change)
		return True

	def check_vpls (self, scope, configuration):
		nlri = scope[-1]['announce'][-1].nlri

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
