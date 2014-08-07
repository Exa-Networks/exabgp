# encoding: utf-8
"""
bgp.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2014 Exa Networks. All rights reserved.
"""

from exabgp.configuration.engine.registry import Raised
from exabgp.configuration.engine.section import Section


# =================================================================== bmp_syntax

syntax_bmp = """\
bmp {
	lots here
}
""".replace('\t','   ')


# ================================================================ RaisedProcess

class RaisedBMP (Raised):
	syntax = syntax_bmp


# =================================================================== SectionBMP
#

class SectionBMP (Section):
	content = None
	syntax = syntax_bmp

	@classmethod
	def register (cls,registry,location):
		registry.register_class(cls)

		registry.register_hook(cls,'enter',location,'enter_unamed_section')
		registry.register_hook(cls,'exit',location,'exit_unamed_section')
