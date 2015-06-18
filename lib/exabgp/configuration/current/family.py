# encoding: utf-8
"""
parse_family.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.configuration.current.generic import Generic


class ParseFamily (Generic):
	syntax = \
		'syntax:\n' \
		'family {\n' \
		'   all;      # default if not family block is present, announce all we know\n' \
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

	action = {
		'ipv4':  ['append'],
		'ipv6':  ['append'],
		'l2vpn': ['append'],
	}

	name = 'family'

	def __init__ (self, tokeniser, scope, error, logger):
		Generic.__init__(self,tokeniser,scope,error,logger)
		self.known = {
			'ipv4':  self.ipv4,
			'ipv6':  self.ipv6,
			'l2vpn': self.l2vpn,
		}
		self._all = ''
		self._seen = []

	def clear (self):
		self._all = False
		self._seen = []

	def pre (self):
		self.clear()
		return True

	def post (self):
		return True

	def _family (self, tokeniser, afi):
		if self._all:
			raise ValueError('can not add any family once family all is set')

		safi = tokeniser().lower()

		pair = self.convert[afi].get(safi,None)
		if not pair:
			raise ValueError('invalid afi/safi pair %s/%s' % (afi,safi))
		if pair in self._seen:
			raise ValueError('duplicate afi/safi pair %s/%s' % (afi,safi))
		self._seen.append(pair)
		return pair

	def ipv4 (self, tokeniser):
		return self._family(tokeniser, 'ipv4')

	def ipv6 (self, tokeniser):
		return self._family(tokeniser, 'ipv6')

	def l2vpn (self, tokeniser):
		return self._family(tokeniser, 'l2vpn')

	def minimal (self, tokeniser):
		raise ValueError('family minimal is deprecated')

	def all (self, tokeniser):
		if self._all or self._seen:
			return self.error.set('all can not be used with any other options')
		self._all = True
		raise RuntimeError('not implemented yet')
