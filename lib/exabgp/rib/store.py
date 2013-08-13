# encoding: utf-8
"""
store.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.direction import OUT
from exabgp.bgp.message.update import Update

# XXX: FIXME: we would not have to use so many setdefault if we pre-filled the dicts with the families

class Store (object):
	def __init__ (self,watchdog,cache=True):
		# XXX: FIXME: we can decide to not cache the routes we seen and let the backend do it for us and save the memory
		self._watchdog = watchdog
		self.cache = cache
		self._announced = {}
		self._cache_attribute = {}
		self._modify_nlri = {}
		self._modify_sorted = {}


	def every_changes (self):
		# we use list() to make a snapshot of the data at the time we run the command
		for family in list(self._watchdog.filtered(self._announced.keys())):
			for change in self._announced[family].values():
				yield change

	def dump (self):
		# This function returns a hash and not a list as "in" tests are O(n) with lists and O(1) with hash
		# and with ten thousands routes this makes an enormous difference (60 seconds to 2)
		changes = {}
		for family in self._announced.keys():
			for change in self._announced[family].values():
				changes[change.index()] = change
		return changes


	def resend_known (self):
		for change in self.every_changes():
			self.insert_change(change,True)


	def add_change (self,change):
		watchdog = change.attributes.watchdog()
		withdraw = change.attributes.withdraw()
		self._watchdog.integrate(change,watchdog,withdraw)
		return True

	def insert_change (self,change,force=False):
		# WARNING : this function can run while we are in the updates() loop

		# self._announced[fanily][nlri-index] = change

		# XXX: FIXME: if we fear a conflict of nlri-index between family (very very unlikely)
		# XXX: FIXME: then we should preprend the index() with the AFI and SAFI

		# self._modify_nlri[nlri-index] = change : we are modifying this nlri
		# self._modify_sorted[attr-index][nlri-index] = change : add or remove the nlri
		# self._cache_attribute[attr-index] = change
		# and it allow to overwrite change easily :-)

		# import traceback
		# traceback.print_stack()
		# print "inserting", change.extensive()

		change_nlri_index = change.nlri.index()
		change_attr_index = change.attributes.index()

		dict_sorted = self._modify_sorted
		dict_nlri = self._modify_nlri
		dict_attr = self._cache_attribute

		if change_nlri_index in dict_nlri and not force:
			old_attr_index = dict_nlri[change_nlri_index].attributes.index()
			# pop removes the entry
			old_change = dict_nlri.pop(change_nlri_index)
			# do not delete dict_attr, other routes may use it
			del dict_sorted[old_attr_index][change_nlri_index]
			if not dict_sorted[old_attr_index]:
				del dict_sorted[old_attr_index]
			if old_change.nlri.action == OUT.announce and change.nlri.action == OUT.withdraw:
				return True

		dict_sorted.setdefault(change_attr_index,{})[change_nlri_index] = change
		dict_nlri[change_nlri_index] = change
		if change_attr_index not in dict_attr:
			dict_attr[change_attr_index] = change

		if change.nlri.action == OUT.withdraw:
			if not self.cache:
				return True
			return change_nlri_index in self._announced or change_nlri_index in dict_nlri
		return True

	def updates (self,grouped):

		# changes = self._watchdog.announce()
		# if changes:
		# 	for change in changes:
		# 		yield Update().new(change.nlri,change.attributes)

		dict_sorted = self._modify_sorted
		dict_nlri = self._modify_nlri
		dict_attr = self._cache_attribute

		for attr_index,dict_new_nlri in list(dict_sorted.iteritems()):
			attributes = dict_attr[attr_index].attributes

			# we NEED the copy provided by list() here as clear_sent or insert_change can be called while we iterate
			changed = list(dict_new_nlri.itervalues())
			dict_del = dict_sorted[attr_index]

			if grouped:
				yield Update().new([dict_nlri[nlri_index].nlri for nlri_index in dict_new_nlri],attributes)
				for change in changed:
					nlri_index = change.nlri.index()
					del dict_del[nlri_index]
					del dict_nlri[nlri_index]
			else:
				for change in changed:
					nlri = change.nlri
					yield Update().new([nlri,],attributes)
					nlri_index = nlri.index()
					del dict_del[nlri_index]
					del dict_nlri[nlri_index]

			if self.cache:
				announced = self._announced
				for change in changed:
					if change.nlri.action == OUT.announce:
						announced.setdefault(change.nlri.family(),{})[change.nlri.index()] = change
					else:
						family = change.nlri.family()
						if family in announced:
							announced[family].pop(change.nlri.index(),None)

		# cleanup, as we can not be sure it was not modified when we were running
		if not self._modify_nlri:
			self._modify_sorted = {}


	def clear_sent (self):
		# WARNING : this function can run while we are in the updates() loop
		self._modify_nlri = {}
		self._modify_sorted = {}
