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

	def __init__ (self,name,families,new=False):
		if name in self._cache:
			self.incoming = self._cache[name].incoming
			self.outgoing = self._cache[name].outgoing
			self.resend(None,False)
		else:
			self.incoming = Store(False,families)
			self.outgoing = Store(True,families)
			self._cache[name] = self

	def reset (self):
		self.incoming.reset()
		self.outgoing.reset()

	def resend (self,send_families,enhanced_refresh):
		self.outgoing.resend(send_families,enhanced_refresh)
