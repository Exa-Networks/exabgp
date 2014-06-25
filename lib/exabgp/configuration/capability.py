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

class Capability (Registry,Data):
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

	@classmethod
	def register (cls,location):
		cls.register_class(cls)

		cls.register_hook('enter',location,cls,'enter')
		cls.register_hook('exit',location,cls,'exit')

		cls.register_hook('action',location+['asn4'],Capability,'asn4')
		cls.register_hook('action',location+['aigp'],Capability,'aigp')
		cls.register_hook('action',location+['add-path'],Capability,'addpath')
		cls.register_hook('action',location+['operational'],Capability,'operational')
		cls.register_hook('action',location+['route-refresh'],Capability,'refresh')
		cls.register_hook('action',location+['multi-session'],Capability,'multisession')
		cls.register_hook('action',location+['graceful-restart'],Capability,'graceful')


Capability.register(['capability'])
