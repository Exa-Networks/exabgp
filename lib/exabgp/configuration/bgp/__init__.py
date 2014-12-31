# encoding: utf-8
"""
bgp.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.engine.registry import Raised
from exabgp.configuration.engine.section import Section


# =================================================================== bgp_syntax

syntax_bgp = """\
bgp {
	lots here
}
"""


# ================================================================ RaisedProcess

class RaisedBGP (Raised):
	syntax = syntax_bgp


# =================================================================== SectionBGP
#

class SectionBGP (Section):
	syntax = syntax_bgp
	name = 'bgp'
	content = None

	@classmethod
	def register (cls,registry,location):
		registry.register_class(cls)

		registry.register_hook(cls,'enter',location,'enter_unamed_section')
		registry.register_hook(cls,'exit',location,'exit_unamed_section')
