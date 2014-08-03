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


# ============================================================ capability_syntax

capability_syntax = \
'capability <name> {\n' \
'   asn4 enable|disable                         # default enabled\n' \
'   aigp enable|disable                         # default disabled\n' \
'   operational enable|disable                  # default disabled\n' \
'   multi-session enable|disable                # default disabled\n' \
'   route-refresh enable|disable                # default disabled\n' \
'   graceful-restart <time in second>           # default disabled\n' \
'   add-path disable|send|receive|send/receive  # default disabled\n' \
'}\n'


# ============================================================= RaisedCapability

class RaisedCapability (Raised):
	syntax = capability_syntax


# ============================================================ SectionCapability
#

class SectionCapability (Entry):
	syntax = capability_syntax
	name = 'capability'

	def enter (self,tokeniser):
		self.content = self.section_name(self.name,tokeniser)

	def exit (self,tokeniser):
		# no verification to do
		pass

	def asn4 (self,tokeniser):
		self._check_duplicate(tokeniser,RaisedCapability)
		self.content[Capability.ID(Capability.ID.FOUR_BYTES_ASN)] = boolean(tokeniser,True)

	def aigp (self,tokeniser):
		self._check_duplicate(tokeniser,RaisedCapability)
		self.content[Capability.ID(Capability.ID.AIGP)] = boolean(tokeniser,False)

	def addpath (self,tokeniser):
		self._check_duplicate(tokeniser,RaisedCapability)
		valid_options = ('receive','send','send/receive','disable','disabled')
		ap = tokeniser()
		if ap not in valid_options:
			raise RaisedCapability(tokeniser,"%s is not a invalid add-path paramerter, options are %s" % (ap,', '.join(valid_options)))

		self.content[Capability.ID(Capability.ID.ADD_PATH)] = 0
		if ap.endswith('receive'): self.content[Capability.ID.ADD_PATH] += 1
		if ap.startswith('send'):  self.content[Capability.ID.ADD_PATH] += 2

	def operational (self,tokeniser):
		self._check_duplicate(tokeniser,RaisedCapability)
		self.content[Capability.ID(Capability.ID.OPERATIONAL)] = boolean(tokeniser,False)

	def refresh (self,tokeniser):
		self._check_duplicate(tokeniser,RaisedCapability)
		self.content[Capability.ID(Capability.ID.ROUTE_REFRESH)] = boolean(tokeniser,False)

	def multisession (self,tokeniser):
		self._check_duplicate(tokeniser,RaisedCapability)
		self.content[Capability.ID(Capability.ID.MULTISESSION_CISCO)] = boolean(tokeniser,False)

	def graceful (self,tokeniser):
		self._check_duplicate(tokeniser,RaisedCapability)
		token = tokeniser()
		if not token.isdigit():
			raise RaisedCapability(tokeniser,"%s is not a valid option for graceful-restart, it must be a positive number smaller than 2^16" % token)

		duration = int(token)
		if duration < 0:
			raise RaisedCapability(tokeniser,"%s is not a valid option for graceful-restart, it must be a positive number smaller than 2^16" % token)
		if duration > pow(2,16):
			raise RaisedCapability(tokeniser,"%s is not a valid option for graceful-restart, it must be a positive number smaller than 2^16" % token)

		self.content[Capability.ID(Capability.ID.GRACEFUL_RESTART)] = duration

	@classmethod
	def register (cls,registry,location):
		registry.register_class(cls)

		registry.register_hook(cls,'enter',location,'enter')
		registry.register_hook(cls,'exit',location,'exit')

		registry.register_hook(cls,'action',location+['asn4'],'asn4')
		registry.register_hook(cls,'action',location+['aigp'],'aigp')
		registry.register_hook(cls,'action',location+['add-path'],'addpath')
		registry.register_hook(cls,'action',location+['operational'],'operational')
		registry.register_hook(cls,'action',location+['route-refresh'],'refresh')
		registry.register_hook(cls,'action',location+['multi-session'],'multisession')
		registry.register_hook(cls,'action',location+['graceful-restart'],'graceful')
