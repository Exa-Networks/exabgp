# encoding: utf-8
"""
session.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.engine.raised import Raised
from exabgp.configuration.engine.section import Section
from exabgp.configuration.engine.parser import ip
from exabgp.configuration.engine.parser import holdtime

from exabgp.configuration.bgp.capability import syntax_capability
from exabgp.configuration.bgp.capability import SectionCapability

from exabgp.configuration.bgp.asn import SectionASN
from exabgp.configuration.bgp.asn import syntax_asn


# ============================================================== syntax_session

syntax_session = """\
session <name> {
	%s
	%s
}
""" % (
	'\n\t'.join((_.replace(' <name>','') for _ in syntax_asn.split('\n'))),
	'\n\t'.join((_.replace(' <name>','') for _ in syntax_capability.split('\n'))),
)


# =============================================================== RaisedSession

class RaisedSession (Raised):
	syntax = syntax_session


# ============================================================== SectionSession
#

class SectionSession (Section):
	syntax = syntax_session
	name = 'session'

	def exit (self, tokeniser):
		asn = self.extract_anonymous('asn',tokeniser)
		if asn:
			if 'asn' in self.content:
				raise RaisedSession(tokeniser,"can not have amed and anonymous 'asn' in a session")
			self.content['asn'] = asn

		if 'asn' not in self.content:
			raise RaisedSession(tokeniser,"section is missing a 'asn' section")

		capability = self.extract_anonymous('capability',tokeniser)
		if capability:
			if 'capability' in self.content:
				raise RaisedSession(tokeniser,"can not have amed and anonymous 'capability' in a session")
			self.content['capability'] = capability

		if 'capability' not in self.content:
			raise RaisedSession(tokeniser,"section is missing a 'capability' section")

		if 'router-id' not in self.content:
			# 0.0.0.0 is now a invlid router-id so it will be replaced by the bind ip
			self.content['router-id'] = ip(lambda:'0.0.0.0')

		if 'hold-time' not in self.content:
			self.content['hold-time'] = holdtime(lambda:'180')

	def router_id (self, tokeniser):
		try:
			self.content['router-id'] = ip(tokeniser)
		except ValueError,exc:
			raise RaisedSession(tokeniser,'could not parse router-id, %s' % str(exc))

	def hold_time (self, tokeniser):
		try:
			self.content['hold-time'] = holdtime(tokeniser)
		except ValueError,exc:
			raise RaisedSession(tokeniser,'could not parse hold-time, %s' % str(exc))

	def asn (self, tokeniser):
		section = self.get_section(SectionASN.name,tokeniser)
		if section:
			self.content['asn'] = section
		else:
			return False

	def capability (self, tokeniser):
		section = self.get_section(SectionCapability.name,tokeniser)
		if section:
			self.content['capability'] = section
		else:
			return False

	@classmethod
	def register (cls, registry, location):
		registry.register_class(cls)

		registry.register(SectionASN,location+['asn'])
		registry.register_hook(cls,'action',location+['asn'],'asn')

		registry.register(SectionCapability,location+['capability'])
		registry.register_hook(cls,'action',location+['capability'],'capability')

		registry.register_hook(cls,'enter',location,'enter')
		registry.register_hook(cls,'exit',location,'exit')

		registry.register_hook(cls,'action',location+['router-id'],'router_id')
		registry.register_hook(cls,'action',location+['hold-time'],'hold_time')

		# registry.register_hook(cls,'enter',location,'enter_nameless')
		# registry.register_hook(cls,'action',location+['local'],'local_asn')
		# registry.register_hook(cls,'action',location+['peer'],'peer_asn')
		# registry.register_hook(cls,'exit', location,'exit_nameless')
