# encoding: utf-8
"""
bgp.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2014 Exa Networks. All rights reserved.
"""

from exabgp.configuration.engine.registry import Entry


# =================================================================== SectionBGP
#

class SectionBGP (Entry):
	content = None

	@classmethod
	def register (cls,registry,location):
		registry.register_class(cls)

		registry.register_hook(cls,'enter',location,'unamed_enter')
		registry.register_hook(cls,'exit',location,'unamed_exit')
