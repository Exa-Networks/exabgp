# encoding: utf-8
"""
family.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.configuration.registry import Registry

from exabgp.protocol.family import AFI,SAFI

# from exabgp.protocol.family import AFI,SAFI,known_families

class Family (object):
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


	def __init__ (self,parser):
		self.parser = parser
		self.content = []

	def enter (self,registry,tokeniser):
		token = tokeniser()
		if token != '{': raise Exception(self.syntax)
		if 'families' in self.content:
			raise Exception('duplicate family blocks')
		self.content = []

	def exit (self,registry,tokeniser):
		# no verification to do
		pass

	def inet (self,registry,tokeniser):
		raise Exception("the word inet is deprecated, please use ipv4 instead",'error')

	def inet4 (self,registry,tokeniser):
		raise Exception("the word inet4 is deprecated, please use ipv4 instead",'error')

	def inet6 (self,registry,tokeniser):
		raise Exception("the word inet6 is deprecated, please use ipv6 instead",'error')

	def _check_conflict (self):
		if 'all' in self.content:
			raise Exception('ipv4 can not be used with all or minimal')
		if 'minimal' in self.content:
			raise Exception('ipv4 can not be used with all or minimal')

	def _drop_colon (self,tokeniser):
		if tokeniser() != ';':
			raise Exception('missing semi-colon')

	def ipv4 (self,registry,tokeniser):
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
			raise Exception('unknow family safi %s' % safi)

		self._drop_colon(tokeniser)

	def ipv6 (self,registry,tokeniser):
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
			raise Exception('unknow family safi %s' % safi)

		self._drop_colon(tokeniser)


	def l2vpn (self,registry,tokeniser):
		self._check_conflict()
		safi = tokeniser()

		if safi == 'vpls':
			self.content.append((AFI(AFI.l2vpn),SAFI(SAFI.vpls)))
		else:
			raise Exception('unknow family safi %s' % safi)

		self._drop_colon(tokeniser)

	def all (self,registry,tokeniser):
		self._check_conflict()
		# bad, we are changing the type
		self.content = ['all',]
		self._drop_colon(tokeniser)

	def minimal (self,registry,tokeniser):
		self._check_conflict()
		# bad, we are changing the type
		self.content = ['minimal',]
		self._drop_colon(tokeniser)


# Not sure about this API yet ..
Registry.register_class(Family)

# Correct registration
Registry.register('enter',['family'],Family,'enter')
Registry.register('exit',['family'],Family,'exit')

Registry.register('action',['family','inet'],Family,'inet')
Registry.register('action',['family','inet4'],Family,'inet4')
Registry.register('action',['family','inet6'],Family,'inet6')
Registry.register('action',['family','ipv4'],Family,'ipv4')
Registry.register('action',['family','ipv6'],Family,'ipv6')
Registry.register('action',['family','l2vpn'],Family,'l2vpn')

Registry.register('action',['family','all'],Family,'all')
Registry.register('action',['family','minimal'],Family,'minimal')

