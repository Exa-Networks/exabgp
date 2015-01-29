# encoding: utf-8
"""
show/__init__.py

Created by Thomas Mangin on 2015-01-15.
Copyright (c) 2015-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.engine.raised import Raised
from exabgp.configuration.engine.section import Section

from exabgp.configuration.environment import environment
from exabgp.version import version

# ================================================================== show_syntax

syntax_show = """\
show {
	version
}
"""


# ================================================================ RaisedProcess

class RaisedShow (Raised):
	syntax = syntax_show


# ================================================================== SectionShow
#

class SectionShow (Section):
	syntax = syntax_show
	name = 'show'

	def enter_show (self, tokeniser):
		Section.enter_anonymous(self,tokeniser)

	def exit_show (self, tokeniser):
		pass

	def version (self, tokeniser):
		self.content['version'] = '%s %s' % (environment.application,version)
		#self.content['version'] = '%s %s' % (environment.application,environment.version)

	@classmethod
	def register (cls, registry, location):
		registry.register_class(cls)

		registry.register_hook(cls,'enter',location,'enter_show')
		registry.register_hook(cls,'action',location+['version'],'version')
		registry.register_hook(cls,'exit', location,'exit_show')
