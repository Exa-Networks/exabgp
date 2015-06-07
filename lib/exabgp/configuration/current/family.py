# encoding: utf-8
"""
parse_family.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.configuration.current.basic import Basic


class ParseFamily (Basic):
	syntax = \
		'syntax:\n' \
		'family {\n' \
		'   all;      # default if not family block is present, announce all we know\n' \
		'   minimal   # use the AFI/SAFI required to announce the routes in the configuration\n' \
		'   \n' \
		'   ipv4 unicast;\n' \
		'   ipv4 multicast;\n' \
		'   ipv4 nlri-mpls;\n' \
		'   ipv4 mpls-vpn;\n' \
		'   ipv4 flow;\n' \
		'   ipv4 flow-vpn;\n' \
		'   ipv6 unicast;\n' \
		'   ipv6 flow;\n' \
		'   ipv6 flow-vpn;\n' \
		'   l2vpn vpls;\n' \
		'   l2vpn evpn;\n' \
		'}\n'

	convert = {
		'ipv4': {
			'unicast':   (AFI(AFI.ipv4),SAFI(SAFI.unicast)),
			'multicast': (AFI(AFI.ipv4),SAFI(SAFI.multicast)),
			'nlri-mpls': (AFI(AFI.ipv4),SAFI(SAFI.nlri_mpls)),
			'mpls-vpn':  (AFI(AFI.ipv4),SAFI(SAFI.mpls_vpn)),
			'flow':      (AFI(AFI.ipv4),SAFI(SAFI.flow_ip)),
			'flow-vpn':  (AFI(AFI.ipv4),SAFI(SAFI.flow_vpn)),
		},
		'ipv6': {
			'unicast':   (AFI(AFI.ipv6),SAFI(SAFI.unicast)),
			'mpls-vpn':  (AFI(AFI.ipv6),SAFI(SAFI.mpls_vpn)),
			'flow':      (AFI(AFI.ipv6),SAFI(SAFI.flow_ip)),
			'flow-vpn':  (AFI(AFI.ipv6),SAFI(SAFI.flow_vpn)),
		},
		'l2vpn': {
			'vpls':      (AFI(AFI.l2vpn),SAFI(SAFI.vpls)),
			'evpn':      (AFI(AFI.l2vpn),SAFI(SAFI.evpn)),
		}
	}

	def __init__ (self, error):
		self.error = error
		self._family = False

	def clear (self):
		self._family = False

	def _set_family (self, scope, tokens, afi):
		if self._family:
			return self.error.set('ipv4 can not be used with all or minimal')

		try:
			safi = tokens.pop(0).lower()
		except IndexError:
			return self.error.set('missing family safi')

		pair = self.convert[afi].get(safi,None)
		if pair:
			scope[-1]['families'].append(pair)
			return True

		return self.error.set('unvalid safi %s for afi %s' % (safi,afi))

	def ipv4 (self, scope, name, command, tokens):
		return self._set_family(scope, tokens, 'ipv4')

	def ipv6 (self, scope, name, command, tokens):
		return self._set_family(scope, tokens, 'ipv6')

	def l2vpn (self, scope, name, command, tokens):
		return self._set_family(scope, tokens, 'l2vpn')

	def minimal (self, scope, name, command, tokens):
		if scope[-1]['families']:
			return self.error.set('minimal can not be used with any other options')

		scope[-1]['families'] = 'minimal'
		self._family = True
		return True

	def all (self, scope, name, command, tokens):
		if scope[-1]['families']:
			return self.error.set('all can not be used with any other options')

		scope[-1]['families'] = 'all'
		self._family = True
		return True
