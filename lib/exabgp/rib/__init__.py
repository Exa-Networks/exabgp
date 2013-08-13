# encoding: utf-8
"""
rib/__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""

from exabgp.rib.watchdog import Watchdog
from exabgp.rib.store import Store

class RIB:
	ribs = {}

	def __init__ (self,name):
		if name in self.ribs:
			return self.ribs[name]
		self.ribs[name] = self

		self.watchdog = Watchdog()
		self.incoming = Store(self.watchdog)
		self.outgoing = Store(self.watchdog)
