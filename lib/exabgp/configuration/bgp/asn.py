# encoding: utf-8
"""
asn.py

Created by Thomas Mangin on 2015-01-15.
Copyright (c) 2015-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.engine.raised import Raised
from exabgp.configuration.engine.section import Section
from exabgp.configuration.engine.parser import asn


# =================================================================== syntax_asn

syntax_asn = """\
asn {
	local <asn>
	peer  <asn>
}
"""


# ==================================================================== RaisedASN

class RaisedASN (Raised):
	syntax = syntax_asn


# =================================================================== ASNSession
#

class SectionASN (Section):
	syntax = syntax_asn
	name = 'asn'

	def enter_asn (self, tokeniser):
		Section.enter(self,tokeniser)

	def exit_asn (self, tokeniser):
		if 'local' not in self.content:
			raise RaisedASN(tokeniser,'section is missing a local asn')

		if 'peer' not in self.content:
			raise RaisedASN(tokeniser,'section is missing a peer asn')

	def local_asn (self, tokeniser):
		try:
			self.content['local'] = asn(tokeniser)
		except ValueError,exc:
			raise RaisedASN(tokeniser,'could not parse local asn, %s' % str(exc))

	def peer_asn (self, tokeniser):
		try:
			self.content['peer'] = asn(tokeniser)
		except ValueError,exc:
			raise RaisedASN(tokeniser,'could not parse peer asn, %s' % str(exc))

	@classmethod
	def register (cls, registry, location):
		registry.register_class(cls)

		registry.register_hook(cls,'enter',location,'enter_asn')
		registry.register_hook(cls,'action',location+['local'],'local_asn')
		registry.register_hook(cls,'action',location+['peer'],'peer_asn')
		registry.register_hook(cls,'exit', location,'exit_asn')
