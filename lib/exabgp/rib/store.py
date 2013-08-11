# encoding: utf-8
"""
store.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

class Store (object):
	def __init__ (self):
		#self.nlris = {}
		#self.attributes = {}
		self._announced = {}

	def every_changes (self):
		for family in list(self._announced.keys()):
			for update in self._announced[family]:
				yield update

	def _all (self):
		# This is a list, only here as an API for watchdog ..
		# Test in list are O(n)

		# we use list() to make a snapshot of the data at the time we run the command
		# XXX: FIXME: is it really needed ... I believe it was added to fix a bug - not sure anymore
		for family in list(self._announced.keys()):
				for change in self._announced[family]:
					yield change

	def dump (self):
		# This function returns a hash and not a list as "in" tests are O(n) with lists and O(1) with hash
		# and with ten thousands routes this makes an enormous difference (60 seconds to 2)
		changes = {}
		for change in self._all():
			changes[change.index()] = change
		return changes

	def add_change (self,change):
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
