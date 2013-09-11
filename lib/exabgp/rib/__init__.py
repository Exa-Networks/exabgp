# encoding: utf-8
"""
rib/__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""

from exabgp.rib.store import Store

class RIB:
	ribs = {}

	def __init__ (self,name):
		if name not in self.ribs:
			self.ribs[name] = self
			self.incoming = Store(False)
			self.outgoing = Store(True)
		else:
			self.incoming = self.ribs[name].incoming
			self.outgoing = self.ribs[name].outgoing
