# encoding: utf-8
"""
family.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2014 Exa Networks. All rights reserved.
"""

from exabgp.configuration.engine.registry import Raised
from exabgp.configuration.engine.registry import Entry
from exabgp.configuration.engine.parser import boolean

from exabgp.bgp.message.open.capability import Capability

# =================================================================== Capability
#

class CapabilitySection (Entry):
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
		self.content[Capability.ID.FOUR_BYTES_ASN] = boolean(tokeniser,True)
		self._drop_colon(tokeniser)

	def aigp (self,tokeniser):
		self.content[Capability.ID.AIGP] = boolean(tokeniser,False)
		self._drop_colon(tokeniser)

	def addpath (self,tokeniser):
		ap = tokeniser()
		if ap not in ('receive','send','send/receive','disable','disabled'):
			raise Raised("")

		self.content[Capability.ID.ADD_PATH] = 0
		if ap.endswith('receive'): self.content[Capability.ID.ADD_PATH] += 1
		if ap.startswith('send'):  self.content[Capability.ID.ADD_PATH] += 2

		self._drop_colon(tokeniser)

	def operational (self,tokeniser):
		self.content[Capability.ID.OPERATIONAL] = boolean(tokeniser,False)
		self._drop_colon(tokeniser)

	def refresh (self,tokeniser):
		self.content[Capability.ID.ROUTE_REFRESH] = boolean(tokeniser,False)
		self._drop_colon(tokeniser)

	def multisession (self,tokeniser):
		self.content[Capability.ID.MULTISESSION_BGP] = boolean(tokeniser,False)
		self._drop_colon(tokeniser)

	def graceful (self,tokeniser):
		token = tokeniser()
		if not token.isdigit():
			raise Raised("")

		duration = int(token)
		if duration < 0:
			raise Raised("")
		if duration > pow(2,16):
			raise Raised("")

		self.content[Capability.ID.GRACEFUL_RESTART] = duration
		self._drop_colon(tokeniser)

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


CapabilitySection.register(['capability'])
