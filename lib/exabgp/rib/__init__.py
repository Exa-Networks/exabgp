# encoding: utf-8
"""
rib/__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.rib.incoming import IncomingRIB
from exabgp.rib.outgoing import OutgoingRIB


class RIB (object):

	# when we perform a configuration reload using SIGUSR, we must not use the RIB
	# without the cache, all the updates previously sent via the API are lost

	_cache = {}

	def __init__ (self, name, adj_rib_in, adj_rib_out, families):
		self.name = name

		if name in self._cache:
			self.incoming = self._cache[name].incoming
			self.outgoing = self._cache[name].outgoing
			self.incoming.families = families
			self.outgoing.families = families
			self.outgoing.delete_cached_family(families)

			if adj_rib_out:
				self.outgoing.resend(None,False)
			else:
				self.outgoing.clear()
		else:
			self.incoming = IncomingRIB(families)
			self.outgoing = OutgoingRIB(families)
			self._cache[name] = self

		self.outgoing.adj_rib_out = adj_rib_out
		self.outgoing.adj_rib_in = adj_rib_in

	def reset (self):
		self.incoming.reset()
		self.outgoing.reset()

	def uncache(self):
		if self.name in self._cache:
			del self._cache[self.name]

	# This code was never tested ...
	def clear (self):
		self._cache[self.name].incoming = IncomingRIB(self._cache[self.name].incoming.families)
		self._cache[self.name].outgoing = OutgoingRIB(self._cache[self.name].incoming.families)
