# encoding: utf-8
"""
family.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2014 Exa Networks. All rights reserved.
"""

from exabgp.configuration.registry import Raised,Registry

from exabgp.protocol.family import AFI,SAFI

# from exabgp.protocol.family import AFI,SAFI,known_families

class Family (Registry):
	syntax = \
		'family {\n' \
		'#  all;		# default, announce all the families we know\n' \
		'#  minimal; # announce the AFI/SAFI of the routes in the configuration\n' \
		'\n' \
		'   ipv4 unicast;\n' \
		'   ipv4 multicast;\n' \
		'   ipv4 nlri-mpls;\n' \
		'   ipv4 mpls-vpn;\n' \
		'   ipv4 flow;\n' \
		'   ipv4 flow-vpn;\n' \
		'   ipv6 unicast;\n' \
		'   ipv6 flow;\n' \
		'   ipv6 flow-vpn;\n' \
		'}\n'


	def __init__ (self):
		self.content = []

	def enter (self,tokeniser):
		token = tokeniser()
		if token != '{': raise Raised(self.syntax)
		if 'families' in self.content:
			raise Raised('duplicate family blocks')
		self.content = []

	def exit (self,tokeniser):
		# no verification to do
		pass

	def inet (self,tokeniser):
		raise Raised("the word inet is deprecated, please use ipv4 instead",'error')

	def inet4 (self,tokeniser):
		raise Raised("the word inet4 is deprecated, please use ipv4 instead",'error')

	def inet6 (self,tokeniser):
		raise Raised("the word inet6 is deprecated, please use ipv6 instead",'error')

	def _check_conflict (self):
		if 'all' in self.content:
			raise Raised('ipv4 can not be used with all or minimal')
		if 'minimal' in self.content:
			raise Raised('ipv4 can not be used with all or minimal')

	def _drop_colon (self,tokeniser):
		if tokeniser() != ';':
			raise Raised('missing semi-colon')

	def ipv4 (self,tokeniser):
		self._check_conflict()
		safi = tokeniser()

		if safi == 'unicast':
			self.content.append((AFI(AFI.ipv4),SAFI(SAFI.unicast)))
		elif safi == 'multicast':
			self.content.append((AFI(AFI.ipv4),SAFI(SAFI.multicast)))
		elif safi == 'nlri-mpls':
			self.content.append((AFI(AFI.ipv4),SAFI(SAFI.nlri_mpls)))
		elif safi == 'mpls-vpn':
			self.content.append((AFI(AFI.ipv4),SAFI(SAFI.mpls_vpn)))
		elif safi in ('flow'):
			self.content.append((AFI(AFI.ipv4),SAFI(SAFI.flow_ip)))
		elif safi == 'flow-vpn':
			self.content.append((AFI(AFI.ipv4),SAFI(SAFI.flow_vpn)))
		else:
			raise Raised('unknow family safi %s' % safi)

		self._drop_colon(tokeniser)

	def ipv6 (self,tokeniser):
		self._check_conflict()
		safi = tokeniser()

		if safi == 'unicast':
			self.content.append((AFI(AFI.ipv6),SAFI(SAFI.unicast)))
		elif safi == 'mpls-vpn':
			self.content.append((AFI(AFI.ipv6),SAFI(SAFI.mpls_vpn)))
		elif safi in ('flow'):
			self.content.append((AFI(AFI.ipv6),SAFI(SAFI.flow_ip)))
		elif safi == 'flow-vpn':
			self.content.append((AFI(AFI.ipv6),SAFI(SAFI.flow_vpn)))
		else:
			raise Raised('unknow family safi %s' % safi)

		self._drop_colon(tokeniser)


	def l2vpn (self,tokeniser):
		self._check_conflict()
		safi = tokeniser()

		if safi == 'vpls':
			self.content.append((AFI(AFI.l2vpn),SAFI(SAFI.vpls)))
		else:
			raise Raised('unknow family safi %s' % safi)

		self._drop_colon(tokeniser)

	def all (self,tokeniser):
		self._check_conflict()
		# bad, we are changing the type
		self.content = ['all',]
		self._drop_colon(tokeniser)

	def minimal (self,tokeniser):
		self._check_conflict()
		# bad, we are changing the type
		self.content = ['minimal',]
		self._drop_colon(tokeniser)

	@classmethod
	def register (cls,location):
		cls.register_class()

		cls.register_hook('enter',location,'enter')
		cls.register_hook('exit',location,'exit')

		cls.register_hook('action',location+['inet'],'inet')
		cls.register_hook('action',location+['inet4'],'inet4')
		cls.register_hook('action',location+['inet6'],'inet6')
		cls.register_hook('action',location+['ipv4'],'ipv4')
		cls.register_hook('action',location+['ipv6'],'ipv6')
		cls.register_hook('action',location+['l2vpn'],'l2vpn')

		cls.register_hook('action',location+['all'],'all')
		cls.register_hook('action',location+['minimal'],'minimal')


Family.register(['family'])
