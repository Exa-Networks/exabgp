from exabgp.bgp.message.open.capability import Capabilities

# encoding: utf-8
"""
family.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.configuration.registry import Registry,Data

from exabgp.bgp.message.open.capability.id import CapabilityID

# from exabgp.protocol.family import AFI,SAFI,known_families

class Capability (Data):
	syntax = \
	'capability {\n' \
	'   asn4 enable|disable;                         # default enabled\n' \
	'   aigp enable|disable;                         # default disabled\n' \
	'   operational enable|disable;                  # default disabled\n' \
	'   multi-session enable|disable;                # default disabled\n' \
	'   route-refresh enable|disable;                # default disabled\n' \
	'   graceful-restart <time in second>;           # default disabled\n' \
	'   add-path disable|send|receive|send/receive;  # default disabled\n' \
	'}\n'

	def __init__ (self,parser):
		self.parser = parser
		self.content = None

	def enter (self,registry,tokeniser):
		token = tokeniser()
		if token != '{': raise Exception(self.syntax)
		self.content = dict()

	def exit (self,registry,tokeniser):
		# no verification to do
		pass

	def asn4 (self,registry,tokeniser):
		self.content[CapabilityID.FOUR_BYTES_ASN] = self.boolean(tokeniser,True)

	def aigp (self,registry,tokeniser):
		self.content[CapabilityID.AIGP] = self.boolean(tokeniser,False)

	def addpath (self,registry,tokeniser):
		ap = tokeniser()
		if ap not in ('receive','send','send/receive','disable','disabled'):
			raise Exception("")

		self.content[CapabilityID.ADD_PATH] = 0
		if ap.endswith('receive'): self.content[CapabilityID.ADD_PATH] += 1
		if ap.startswith('send'):  self.content[CapabilityID.ADD_PATH] += 2

		self._drop_colon(tokeniser)

	def operational (self,registry,tokeniser):
		self.content[CapabilityID.OPERATIONAL] = self.boolean(tokeniser,False)

	def refresh (self,registry,tokeniser):
		self.content[CapabilityID.ROUTE_REFRESH] = self.boolean(tokeniser,False)

	def multisession (self,registry,tokeniser):
		self.content[CapabilityID.MULTISESSION_BGP] = self.boolean(tokeniser,False)

	def graceful (self,registry,tokeniser):
		token = tokeniser()
		if not token.isdigit():
			raise Exception("")

		duration = int(token)
		if duration < 0:
			raise Exception("")
		if duration > pow(2,16):
			raise Exception("")

		self.content[CapabilityID.GRACEFUL_RESTART] = duration
		self._drop_colon(tokeniser)

	def _drop_colon (self,tokeniser):
		if tokeniser() != ';':
			raise Exception('missing semi-colon')

	def _check_duplicate (self,key):
		if key in self.content:
			raise Exception("")

# Not sure about this API yet ..
Registry.register_class(Capability)

# Correct registration
Registry.register('enter',['capability'],Capability,'enter')
Registry.register('exit',['capability'],Capability,'exit')

Registry.register('action',['capability','asn4'],Capability,'asn4')
Registry.register('action',['capability','aigp'],Capability,'aigp')
Registry.register('action',['capability','add-path'],Capability,'addpath')
Registry.register('action',['capability','operational'],Capability,'operational')
Registry.register('action',['capability','route-refresh'],Capability,'refresh')
Registry.register('action',['capability','multi-session'],Capability,'multisession')
Registry.register('action',['capability','graceful-restart'],Capability,'graceful')
