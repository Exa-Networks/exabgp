# encoding: utf-8
"""
bgp.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.engine.raised import Raised
from exabgp.configuration.engine.section import Section


# =================================================================== bmp_syntax

syntax_bmp = """\
bmp {
	lots here
}
"""


# ================================================================ RaisedProcess

class RaisedBMP (Raised):
	syntax = syntax_bmp


# =================================================================== SectionBMP
#

class SectionBMP (Section):
	syntax = syntax_bmp
	name = 'bmp'
	content = None

	@classmethod
	def register (cls, registry, location):
		registry.register_class(cls)

		registry.register_hook(cls,'enter',location,'enter_nameless')
		registry.register_hook(cls,'exit',location,'exit_nameless')
