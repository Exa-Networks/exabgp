# encoding: utf-8
"""
neighbor.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.engine.raised import Raised
from exabgp.configuration.engine.section import Section
from exabgp.configuration.engine.parser import ip
from exabgp.configuration.engine.parser import ttl
from exabgp.configuration.engine.parser import md5

from exabgp.configuration.bgp.session import SectionSession


# ============================================================== syntax_neighbor

syntax_neighbor = """\
neighbor <name> {
	session <name>
	tcp {
		bind          82.219.212.34
		connect       195.8.215.15"
		ttl-security  disable
		md5           "secret"
	}
	announce [
		local-routes
		off-goes-the-ddos
	]
}
"""

# =============================================================== RaisedNeighbor

class RaisedNeighbor (Raised):
	syntax = syntax_neighbor


# ============================================================== SectionNeighbor


class SectionNeighbor (Section):
	syntax = syntax_neighbor
	name = 'neighbor'

	def enter (self, tokeniser):
		Section.enter(self,tokeniser)

	def exit (self, tokeniser):
		if 'tcp-bind' not in self.content:
			raise RaisedNeighbor('neighbor needs a tcp bind ip')

		if 'tcp-connect' not in self.content:
			raise RaisedNeighbor('neighbor needs a tcp connect ip')

		if 'tcp-ttl-security' not in self.content:
			self.content['tcp-ttl-security'] = None

		if 'tcp-md5' not in self.content:
			self.content['tcp-md5'] = None

	def session (self, tokeniser):
		section = self.get_section(SectionSession.name,tokeniser)
		if section:
			self.content['session'] = section
		else:
			return False

	def announce (self, tokeniser):
		announced = tokeniser()
		if not hasattr(announced,'pop'):
			raise RaisedNeighbor('announce takes a list of named routes')
		self.content['announce'] = [word for (line,column,line,word) in announced]

	def tcp_bind (self, tokeniser):
		try:
			self.content['tcp-bind'] = ip(tokeniser)
		except ValueError,exc:
			raise RaisedNeighbor(tokeniser,'could not parse tcp bind ip, %s' % str(exc))

	def tcp_connect (self, tokeniser):
		try:
			self.content['tcp-connect'] = ip(tokeniser)
		except ValueError,exc:
			raise RaisedNeighbor(tokeniser,'could not parse tcp connect ip, %s' % str(exc))

	def tcp_ttl_security (self, tokeniser):
		try:
			self.content['tcp-ttl-security'] = ttl(tokeniser)
		except ValueError,exc:
			raise RaisedNeighbor(tokeniser,'could not parse tcp ttl, %s' % str(exc))

	def tcp_md5 (self, tokeniser):
		try:
			self.content['tcp-md5'] = md5(tokeniser)
		except ValueError,exc:
			raise RaisedNeighbor(tokeniser,'could not parse tcp MD5, %s' % str(exc))

	@classmethod
	def register (cls, registry, location):
		registry.register_class(cls)

		registry.register_hook(cls,'enter',location,'enter')

		registry.register(SectionSession,location+['session'])
		registry.register_hook(cls,'action',location+['session'],'session')

		registry.register_hook(cls,'action',location+['announce'],'announce')

		for tcp in (location+['tcp'],):
			registry.register_hook(cls,'enter',tcp,'enter_nameless')
			registry.register_hook(cls,'action',tcp+['bind'],'tcp_bind')
			registry.register_hook(cls,'action',tcp+['connect'],'tcp_connect')
			registry.register_hook(cls,'action',tcp+['ttl-security'],'tcp_ttl_security')
			registry.register_hook(cls,'action',tcp+['md5'],'tcp_md5')
			registry.register_hook(cls,'exit', tcp,'exit')


		registry.register_hook(cls,'exit',location,'exit')
