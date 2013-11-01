# encoding: utf-8
"""
rib/__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""

from exabgp.rib.store import Store

class RIB:

	# when we perform a configuration reload using SIGUSR, we must not use the RIB
	# without the cache, all the updates previously sent via the API are lost

	_cache = {}

	def __init__ (self,name,adjribout,families):
		if name in self._cache:
			self.incoming = self._cache[name].incoming
			self.outgoing = self._cache[name].outgoing
			if adjribout:
				self.outgoing.resend(None,False)
			else:
				self.outgoing.clear()
		else:
			self.incoming = Store(families)
			self.outgoing = Store(families)
			self._cache[name] = self

		self.outgoing.cache = adjribout

	def reset (self):
		self.incoming.reset()
		self.outgoing.reset()
