# encoding: utf-8
"""
session.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.engine.registry import Raised
from exabgp.configuration.engine.section import Section
from exabgp.configuration.engine.parser import asn
from exabgp.configuration.engine.parser import ip
from exabgp.configuration.engine.parser import holdtime

from exabgp.configuration.bgp.capability import syntax_capability
from exabgp.configuration.bgp.capability import SectionCapability


# ============================================================== syntax_session

syntax_session = """\
session <name> {
	%s
}
""" % (
	'\n\t'.join((_.replace(' <name>','') for _ in syntax_capability.split('\n')))
)


# =============================================================== RaisedSession

class RaisedSession (Raised):
	syntax = syntax_session


# ============================================================== SectionSession
#

class SectionSession (Section):
	syntax = syntax_session
	name = 'session'

	def exit (self,tokeniser):
		capability = self.get_unamed(tokeniser,'capability')
		if capability:
			if 'capability' in self.content:
				raise RaisedSession(tokeniser,'can not have unamed and named capability in a session')
			self.content['capability'] = capability
		if 'capability' not in self.content:
			raise RaisedSession(tokeniser,'section is missing a capability section')

		if 'router-id' not in self.content:
			# 0.0.0.0 is now a invlid router-id so it will be replaced by the bind ip
			self.content['router-id'] = ip(lambda:'0.0.0.0')

		if 'hold-time' not in self.content:
			self.content['hold-time'] = holdtime(lambda:'180')

		if 'asn-local' not in self.content:
			raise RaisedSession(tokeniser,'section is missing a local asn')

		if 'asn-peer' not in self.content:
			raise RaisedSession(tokeniser,'section is missing a peer asn')

	def router_id (self,tokeniser):
		try:
			self.content['router-id'] = ip(tokeniser)
		except ValueError,e:
			raise RaisedSession(tokeniser,'could not parse router-id, %s' % str(e))

	def hold_time (self,tokeniser):
		try:
			self.content['hold-time'] = holdtime(tokeniser)
		except ValueError,e:
			raise RaisedSession(tokeniser,'could not parse hold-time, %s' % str(e))

	def local_asn (self,tokeniser):
		try:
			self.content['asn-local'] = asn(tokeniser)
		except ValueError,e:
			raise RaisedSession(tokeniser,'could not parse local asn, %s' % str(e))

	def peer_asn (self,tokeniser):
		try:
			self.content['asn-peer'] = asn(tokeniser)
		except ValueError,e:
			raise RaisedSession(tokeniser,'could not parse peer asn, %s' % str(e))

	def capability (self,tokeniser):
		section = self.get_section(SectionCapability.name,tokeniser)
		if section:
			self.content['capability'] = section
		else:
			return False

	@classmethod
	def register (cls,registry,location):
		registry.register_class(cls)

		registry.register(SectionCapability,location+['capability'])
		registry.register_hook(cls,'action',location+['capability'],'capability')

		registry.register_hook(cls,'enter',location,'enter')
		registry.register_hook(cls,'exit',location,'exit')

		registry.register_hook(cls,'action',location+['router-id'],'router_id')
		registry.register_hook(cls,'action',location+['hold-time'],'hold_time')

		asn = location + ['asn']
		registry.register_hook(cls,'enter',asn,'enter_unamed_section')
		registry.register_hook(cls,'action',asn+['local'],'local_asn')
		registry.register_hook(cls,'action',asn+['peer'],'peer_asn')
		registry.register_hook(cls,'exit', asn,'exit_unamed_section')
