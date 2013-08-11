# encoding: utf-8
"""
rib/__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""

from exabgp.rib.watchdog import Watchdog
from exabgp.rib.store import Store

class OutStore (Store):
	def __init__ (self,watchdog):
		self._watchdog = watchdog
		Store.__init__(self)

	def add_change (self,change):
		watchdog = change.attributes.watchdog()
		withdraw = change.attributes.withdraw()
		self._watchdog.integrate(change,watchdog,withdraw)
		Store.add_change(self,change)
		return True

	def dump (self):
		# This function returns a hash and not a list as "in" tests are O(n) with lists and O(1) with hash
		# and with ten thousands routes this makes an enormous difference (60 seconds to 2)
		changes = {}
		for change in self._watchdog.filtered(self._all()):
			changes[change.index()] = change
		return changes

InStore = Store

class RIB:
	watchdog = Watchdog()
	incoming = InStore()
	outgoing = OutStore(watchdog)
