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


	append = convert.keys()

	name = 'family'

	def __init__ (self, tokeniser, scope, error, logger):
		Generic.__init__(self,tokeniser,scope,error,logger)
		self._full = ''
		self.known = {
			'ipv4':  self.ipv4,
			'ipv6':  self.ipv6,
			'l2vpn': self.l2vpn,
		}

	def clear (self):
		self._full = False

	def pre (self):
		self.clear()
		self.scope.to_context()
		return True

	def post (self):
		return True

	def _family (self, tokeniser, afi):
		safi = tokeniser().lower()

		pair = self.convert[afi].get(safi,None)
		if not pair:
			raise ValueError('unvalid safi %s for afi %s' % (safi,afi))
		return pair

	# def family (self, tokens, afi):
	# 	if self._family:
	# 		return self.error.set('ipv4 can not be used with all or minimal')
	#
	# 	try:
	# 		safi = tokens.pop(0).lower()
	# 	except IndexError:
	# 		return self.error.set('missing family safi')
	#
	# 	pair = self.convert[afi].get(safi,None)
	# 	if pair:
	# 		self.scope.content[-1]['families'].append(pair)
	# 		return True
	#
	# 	return self.error.set('unvalid safi %s for afi %s' % (safi,afi))

	def ipv4 (self, tokeniser):
		return self._family(tokeniser, 'ipv4')

	def ipv6 (self, tokeniser):
		return self._family(tokeniser, 'ipv6')

	def l2vpn (self, tokeniser):
		return self._family(tokeniser, 'l2vpn')

	def minimal (self, tokenisers):

		if self.scope.content[-1]['families']:
			return self.error.set('minimal can not be used with any other options')

		self.scope.content[-1]['families'] = 'minimal'
		self._family = True
		return True

	def all (self, tokeniser):
		if self.scope.content[-1]['families']:
			return self.error.set('all can not be used with any other options')

		self.scope.content[-1]['families'] = 'all'
		self._family = True
		return True
