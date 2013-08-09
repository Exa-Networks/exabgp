# encoding: utf-8
"""
store.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update import Update

class Change (object):
	def __init__ (self,nlri,attributes):
		self.nlri = nlri
		self.attributes = attributes

class Store (object):
	def __init__ (self,neighbor):
		#self.nlris = {}
		#self.attributes = {}
		self._updates = {}
		self.neighbor = neighbor

	def every_updates (self):
		for family in list(self._updates.keys()):
			for update in self._updates[family]:
				yield update

	def dump (self):
		# This function returns a hash and not a list as "in" tests are O(n) with lists and O(1) with hash
		# and with ten thousands routes this makes an enormous difference (60 seconds to 2)

		def _updates (self):
			for family in list(self._updates.keys()):
				for update in self._updates[family]:
					yield update

		changes = {}
		for update in self.neighbor.watchdog.filtered(_updates(self)):
			for nlri in update.nlris:
				changes[nlri.pack(True)] = Change(nlri,update.attributes)
		return changes

	def add_update (self,update):
		## XXX: FIXME: we are breaking the update in multiple to make it work for the moment.
		self.neighbor.watchdog.integrate(update)
		print "\n\nsplitting update in many for the moment\n\n"
		for nlri in update.nlris:
			self._updates.setdefault((nlri.afi,nlri.safi),set()).add(Update().new([nlri],update.attributes))
		return True

	def remove_update (self,update):
		try :
			for nlri in update.nlris:
				updates = self._updates[(nlri.afi,nlri.safi)]
				for r in list(updates):
					# XXX: FIXME: we only have one NLRI per route ATM
					if r.nlris[0] == nlri:
						updates.remove(r)
			else:
				updates.remove(update)
		except KeyError:
			pass

	def remove_family (self,family):
		if family in self.families():
			if family in self._routes:
				del self._routes[family]
