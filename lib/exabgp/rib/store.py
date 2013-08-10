# encoding: utf-8
"""
store.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

class Store (object):
	def __init__ (self,neighbor):
		#self.nlris = {}
		#self.attributes = {}
		self._announced = {}
		self.neighbor = neighbor

	def every_changes (self):
		for family in list(self._announced.keys()):
			for update in self._announced[family]:
				yield update

	def dump (self):
		# This function returns a hash and not a list as "in" tests are O(n) with lists and O(1) with hash
		# and with ten thousands routes this makes an enormous difference (60 seconds to 2)

		def _changes (self):
			for family in list(self._announced.keys()):
				for change in self._announced[family]:
					yield change

		changes = {}
		for change in self.neighbor.watchdog.filtered(_changes(self)):
			changes[change.index()] = change
		return changes

	def add_change (self,change):
		watchdog = change.attributes.watchdog()
		withdraw = change.attributes.withdraw()
		self.neighbor.watchdog.integrate(change,watchdog,withdraw)
		self._announced.setdefault((change.nlri.afi,change.nlri.safi),set()).add(change)
		return True

	def remove_change (self,change):
		removed = False
		try :
			announced = self._announced[(change.nlri.afi,change.nlri.safi)]
			for match in list(announced):
				if change.nlri == match.nlri:
					announced.remove(match)
					removed = True
		except KeyError:
			pass
		return removed

	def remove_family (self,family):
		if family in self.families():
			if family in self._routes:
				del self._routes[family]
