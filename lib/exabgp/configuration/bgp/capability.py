# encoding: utf-8
"""
family.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.engine.raised import Raised
from exabgp.configuration.engine.section import Section
from exabgp.configuration.engine.parser import boolean

from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.mp import MultiProtocol

from exabgp.protocol.family import known_families

from exabgp.configuration.bgp.family import SectionFamily
from exabgp.configuration.bgp.family import syntax_family


# ============================================================ syntax_capability

syntax_capability = """\
capability <name> {
	asn4 enable|disable                         # default enabled
	aigp enable|disable                         # default disabled
	operational enable|disable                  # default disabled
	multi-session enable|disable                # default disabled
	route-refresh enable|disable                # default disabled
	graceful-restart <time in second>           # default disabled
	add-path disable|send|receive|send/receive  # default disabled
	%s
}
""" % (
	'\n\t'.join((_.replace(' <name>','') for _ in syntax_family.split('\n')))
)


# ============================================================= RaisedCapability

class RaisedCapability (Raised):
	syntax = syntax_capability


# ============================================================ SectionCapability
#

class SectionCapability (Section):
	syntax = syntax_capability
	name = 'capability'

	def enter (self, tokeniser):
		Section.enter(self,tokeniser)

		self.content[Capability.CODE(Capability.CODE.FOUR_BYTES_ASN)] = True
		self.content[Capability.CODE(Capability.CODE.AIGP)] = False
		self.content[Capability.CODE(Capability.CODE.ADD_PATH)] = 0
		self.content[Capability.CODE(Capability.CODE.OPERATIONAL)] = False
		self.content[Capability.CODE(Capability.CODE.ROUTE_REFRESH)] = False
		self.content[Capability.CODE(Capability.CODE.MULTISESSION)] = False
		self.content[Capability.CODE(Capability.CODE.GRACEFUL_RESTART)] = 0

	def exit (self, tokeniser):
		if Capability.CODE(Capability.CODE.MULTIPROTOCOL) not in self.content:
			self.content[Capability.CODE(Capability.CODE.MULTIPROTOCOL)] = MultiProtocol(known_families())

	def family (self, tokeniser):
		data = self.get_section(SectionFamily.name,tokeniser)
		if data:
			self.content[Capability.CODE(Capability.CODE.MULTIPROTOCOL)] = MultiProtocol((afi,safi) for afi in sorted(data) for safi in sorted(data[afi]))
		else:
			return False

	def asn4 (self, tokeniser):
		self._check_duplicate(tokeniser,RaisedCapability)
		self.content[Capability.CODE(Capability.CODE.FOUR_BYTES_ASN)] = boolean(tokeniser,True)

	def aigp (self, tokeniser):
		self._check_duplicate(tokeniser,RaisedCapability)
		self.content[Capability.CODE(Capability.CODE.AIGP)] = boolean(tokeniser,False)

	def addpath (self, tokeniser):
		self._check_duplicate(tokeniser,RaisedCapability)
		valid_options = ('receive','send','send/receive','disable','disabled')
		ap = tokeniser()
		if ap not in valid_options:
			raise RaisedCapability(tokeniser,"%s is not a invalid add-path paramerter, options are %s" % (ap,', '.join(valid_options)))

		self.content[Capability.CODE(Capability.CODE.ADD_PATH)] = 0
		if ap.endswith('receive'):
			self.content[Capability.CODE.ADD_PATH] += 1
		if ap.startswith('send'):
			self.content[Capability.CODE.ADD_PATH] += 2

	def operational (self, tokeniser):
		self._check_duplicate(tokeniser,RaisedCapability)
		self.content[Capability.CODE(Capability.CODE.OPERATIONAL)] = boolean(tokeniser,False)

	def refresh (self, tokeniser):
		self._check_duplicate(tokeniser,RaisedCapability)
		self.content[Capability.CODE(Capability.CODE.ROUTE_REFRESH)] = boolean(tokeniser,False)

	def multisession (self, tokeniser):
		self._check_duplicate(tokeniser,RaisedCapability)
		self.content[Capability.CODE(Capability.CODE.MULTISESSION_CISCO)] = boolean(tokeniser,False)

	def graceful (self, tokeniser):
		self._check_duplicate(tokeniser,RaisedCapability)
		token = tokeniser()
		if not token.isdigit():
			raise RaisedCapability(tokeniser,"%s is not a valid option for graceful-restart, it must be a positive number smaller than 2^16" % token)

		duration = int(token)
		if duration < 0:
			raise RaisedCapability(tokeniser,"%s is not a valid option for graceful-restart, it must be a positive number smaller than 2^16" % token)
		if duration > pow(2,16):
			raise RaisedCapability(tokeniser,"%s is not a valid option for graceful-restart, it must be a positive number smaller than 2^16" % token)

		self.content[Capability.CODE(Capability.CODE.GRACEFUL_RESTART)] = duration

	@classmethod
	def register (cls, registry, location):
		registry.register_class(cls)

		# FamilySection.register(location)

		registry.register_hook(cls,'enter',location,'enter')
		registry.register_hook(cls,'exit',location,'exit')

		registry.register(SectionFamily,location+['family'])
		registry.register_hook(cls,'action',location+['family'],'family')

		registry.register_hook(cls,'action',location+['asn4'],'asn4')
		registry.register_hook(cls,'action',location+['aigp'],'aigp')
		registry.register_hook(cls,'action',location+['add-path'],'addpath')
		registry.register_hook(cls,'action',location+['operational'],'operational')
		registry.register_hook(cls,'action',location+['route-refresh'],'refresh')
		registry.register_hook(cls,'action',location+['multi-session'],'multisession')
		registry.register_hook(cls,'action',location+['graceful-restart'],'graceful')
