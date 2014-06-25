# encoding: utf-8
"""
family.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2014 Exa Networks. All rights reserved.
"""

from exabgp.configuration.registry import Raised,Registry,Data

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

	def __init__ (self):
		self.content = dict()

	def enter (self,tokeniser):
		token = tokeniser()
		if token != '{': raise Raised(self.syntax)
		self.content = dict()

	def exit (self,tokeniser):
		# no verification to do
		pass

	def asn4 (self,tokeniser):
		self.content[CapabilityID.FOUR_BYTES_ASN] = self.boolean(tokeniser,True)

	def aigp (self,tokeniser):
		self.content[CapabilityID.AIGP] = self.boolean(tokeniser,False)

	def addpath (self,tokeniser):
		ap = tokeniser()
		if ap not in ('receive','send','send/receive','disable','disabled'):
			raise Raised("")

		self.content[CapabilityID.ADD_PATH] = 0
		if ap.endswith('receive'): self.content[CapabilityID.ADD_PATH] += 1
		if ap.startswith('send'):  self.content[CapabilityID.ADD_PATH] += 2

		self._drop_colon(tokeniser)

	def operational (self,tokeniser):
		self.content[CapabilityID.OPERATIONAL] = self.boolean(tokeniser,False)

	def refresh (self,tokeniser):
		self.content[CapabilityID.ROUTE_REFRESH] = self.boolean(tokeniser,False)

	def multisession (self,tokeniser):
		self.content[CapabilityID.MULTISESSION_BGP] = self.boolean(tokeniser,False)

	def graceful (self,tokeniser):
		token = tokeniser()
		if not token.isdigit():
			raise Raised("")

		duration = int(token)
		if duration < 0:
			raise Raised("")
		if duration > pow(2,16):
			raise Raised("")

		self.content[CapabilityID.GRACEFUL_RESTART] = duration
		self._drop_colon(tokeniser)

	def _drop_colon (self,tokeniser):
		if tokeniser() != ';':
			raise Raised('missing semi-colon')

	def _check_duplicate (self,key):
		if key in self.content:
			raise Raised("")

	@classmethod
	def register (cls,location):
		cls.register_class()

		cls.register_hook('enter',location,'enter')
		cls.register_hook('exit',location,'exit')

		cls.register_hook('action',location+['asn4'],'asn4')
		cls.register_hook('action',location+['aigp'],'aigp')
		cls.register_hook('action',location+['add-path'],'addpath')
		cls.register_hook('action',location+['operational'],'operational')
		cls.register_hook('action',location+['route-refresh'],'refresh')
		cls.register_hook('action',location+['multi-session'],'multisession')
		cls.register_hook('action',location+['graceful-restart'],'graceful')


Capability.register(['capability'])
