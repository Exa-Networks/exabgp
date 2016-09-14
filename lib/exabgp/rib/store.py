# encoding: utf-8
"""
store.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI
from exabgp.bgp.message import IN
from exabgp.bgp.message import OUT
from exabgp.bgp.message import Update
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.update.attribute import Attributes


# XXX: FIXME: we would not have to use so many setdefault if we pre-filled the dicts with the families

class Store (object):
	def __init__ (self, families):
		# XXX: FIXME: we can decide to not cache the routes we seen and let the backend do it for us and save the memory
		self._watchdog = {}
		self.cache = False
		self.families = families
		self.clear()

		# clear
		self._cache_attribute = {}
		self._seen = {}
		self._modify_nlri = {}
		self._modify_sorted = {}
		self._changes = None

		# clear + reset
		self._enhanced_refresh_start = []
		self._enhanced_refresh_delay = []

	# will resend all the routes once we reconnect
	def reset (self):
		# WARNING : this function can run while we are in the updates() loop too !
		self._enhanced_refresh_start = []
		self._enhanced_refresh_delay = []
		for update in self.updates(True):
			pass

	# back to square one, all the routes are removed
	def clear (self):
		self._cache_attribute = {}
		self._seen = {}
		self._modify_nlri = {}
		self._modify_sorted = {}
		self._changes = None
		self.reset()

	def sent_changes (self, families=None):
		# families can be None or []
		requested_families = self.families if not families else set(families).intersection(self.families)

		# we use list() to make a snapshot of the data at the time we run the command
		for family in requested_families:
			for change in self._seen.get(family,{}).values():
				if change.nlri.action == OUT.ANNOUNCE:
					yield change

	def resend (self, families, enhanced_refresh):
		# families can be None or []
		requested_families = self.families if not families else set(families).intersection(self.families)

		def _announced (family):
			for change in self._seen.get(family,{}).values():
				if change.nlri.action == OUT.ANNOUNCE:
					yield change
			self._seen[family] = {}

		if enhanced_refresh:
			for family in requested_families:
				if family not in self._enhanced_refresh_start:
					self._enhanced_refresh_start.append(family)
					for change in _announced(family):
						self.insert_announced(change,True)
		else:
			for family in requested_families:
				for change in _announced(family):
					self.insert_announced(change,True)

	# def dump (self):
	# 	# This function returns a hash and not a list as "in" tests are O(n) with lists and O(1) with hash
	# 	# and with ten thousands routes this makes an enormous difference (60 seconds to 2)
	# 	changes = {}
	# 	for family in self._seen.keys():
	# 		for change in self._seen[family].values():
	# 			if change.nlri.action == OUT.ANNOUNCE:
	# 				changes[change.index()] = change
	# 	return changes

	def queued_changes (self):
		for change in self._modify_nlri.values():
			yield change

	def replace (self, previous, changes):
		for change in previous:
			change.nlri.action = OUT.WITHDRAW
			self.insert_announced(change,True)

		for change in changes:
			self.insert_announced(change,True)

	def insert_announced_watchdog (self, change):
		watchdog = change.attributes.watchdog()
		withdraw = change.attributes.withdraw()
		if watchdog:
			if withdraw:
				self._watchdog.setdefault(watchdog,{}).setdefault('-',{})[change.index()] = change
				return True
			self._watchdog.setdefault(watchdog,{}).setdefault('+',{})[change.index()] = change
		self.insert_announced(change)
		return True

	def announce_watchdog (self, watchdog):
		if watchdog in self._watchdog:
			for change in self._watchdog[watchdog].get('-',{}).values():
				change.nlri.action = OUT.ANNOUNCE  # pylint: disable=E1101
				self.insert_announced(change)
				self._watchdog[watchdog].setdefault('+',{})[change.index()] = change
				self._watchdog[watchdog]['-'].pop(change.index())

	def withdraw_watchdog (self, watchdog):
		if watchdog in self._watchdog:
			for change in self._watchdog[watchdog].get('+',{}).values():
				change.nlri.action = OUT.WITHDRAW
				self.insert_announced(change)
				self._watchdog[watchdog].setdefault('-',{})[change.index()] = change
				self._watchdog[watchdog]['+'].pop(change.index())

	def insert_received (self, change):
		if not self.cache:
			return
		elif change.nlri.action == IN.ANNOUNCED:
			self._seen[change.index()] = change
		else:
			self._seen.pop(change.index(),None)

	def insert_announced (self, change, force=False):
		# WARNING: do not call change.nlri.index as it does not prepend the family
		# WARNING : this function can run while we are in the updates() loop

		# self._seen[family][nlri-index] = change

		# self._modify_nlri[nlri-index] = change : we are modifying this nlri
		# self._modify_sorted[attr-index][nlri-index] = change : add or remove the nlri
		# self._cache_attribute[attr-index] = change
		# and it allow to overwrite change easily :-)

		# import traceback
		# traceback.print_stack()
		# print "inserting", change.extensive()

		if not force and self._enhanced_refresh_start:
			self._enhanced_refresh_delay.append(change)
			return

		change_nlri_index = change.index()
		change_attr_index = change.attributes.index()

		dict_sorted = self._modify_sorted
		dict_nlri = self._modify_nlri
		dict_attr = self._cache_attribute

		# removing a route before we had time to announce it ?
		if change_nlri_index in dict_nlri:
			old_attr_index = dict_nlri[change_nlri_index].attributes.index()
			# pop removes the entry
			old_change = dict_nlri.pop(change_nlri_index)
			# do not delete dict_attr, other routes may use it
			del dict_sorted[old_attr_index][change_nlri_index]
			if not dict_sorted[old_attr_index]:
				del dict_sorted[old_attr_index]
			# route removed before announcement, all goo
			if old_change.nlri.action == OUT.ANNOUNCE and change.nlri.action == OUT.WITHDRAW:
				# if we cache sent NLRI and this NLRI was never sent before, we do not need to send a withdrawal
				if self.cache and change_nlri_index not in self._seen.get(change.nlri.family(),{}):
					return

		# add the route to the list to be announced
		dict_sorted.setdefault(change_attr_index,{})[change_nlri_index] = change
		dict_nlri[change_nlri_index] = change
		if change_attr_index not in dict_attr:
			dict_attr[change_attr_index] = change

	def updates (self, grouped):
		if self._changes:
			dict_nlri = self._modify_nlri

			for family in self._seen:
				for change in self._seen[family].itervalues():
					if change.index() not in self._modify_nlri:
						change.nlri.action = OUT.WITHDRAW
						self.insert_announced(change,True)

			for new in self._changes:
				self.insert_announced(new,True)
			self._changes = None
		# end of changes

		rr_announced = []

		for afi,safi in self._enhanced_refresh_start:
			rr_announced.append((afi,safi))
			yield Update(RouteRefresh(afi,safi,RouteRefresh.start),Attributes())

		dict_sorted = self._modify_sorted
		dict_nlri = self._modify_nlri
		dict_attr = self._cache_attribute

		for attr_index,full_dict_change in dict_sorted.items():
			if self.cache:
				dict_change = {}
				for nlri_index,change in full_dict_change.iteritems():
					family = change.nlri.family()
					announced = self._seen.get(family,{})
					if change.nlri.action == OUT.ANNOUNCE:
						if nlri_index in announced:
							old_change = announced[nlri_index]
							# it is a duplicate route
							if old_change.attributes.index() == change.attributes.index() and old_change.nlri.nexthop.index() == change.nlri.nexthop.index():
								continue
					elif change.nlri.action == OUT.WITHDRAW:
						if nlri_index not in announced:
							if dict_nlri[nlri_index].nlri.action == OUT.ANNOUNCE:
								continue
					dict_change[nlri_index] = change
			else:
				dict_change = full_dict_change

			if not dict_change:
				continue

			attributes = dict_attr[attr_index].attributes

			# we NEED the copy provided by list() here as insert_announced can be called while we iterate
			changed = list(dict_change.itervalues())

			if grouped:
				updates = []
				nlris = []
				for change in dict_change.values():
					if change.nlri.afi == AFI.ipv4:
						nlris.append(change.nlri)
						continue
					updates.append(Update([change.nlri],attributes))
				if nlris:
					updates.append(Update(nlris,attributes))
					nlris = []

				for change in changed:
					nlri_index = change.index()
					del dict_sorted[attr_index][nlri_index]
					del dict_nlri[nlri_index]
				# only yield once we have a consistent state, otherwise it will go wrong
				# as we will try to modify things we are using
				for update in updates:
					yield update
			else:
				updates = []
				for change in changed:
					updates.append(Update([change.nlri,],attributes))
					nlri_index = change.index()
					del dict_sorted[attr_index][nlri_index]
					del dict_nlri[nlri_index]
				# only yield once we have a consistent state, otherwise it will go wrong
				# as we will try to modify things we are using
				for update in updates:
					yield update

			if self.cache:
				announced = self._seen
				for change in changed:
					if change.nlri.action == OUT.ANNOUNCE:
						announced.setdefault(change.nlri.family(),{})[change.index()] = change
					else:
						family = change.nlri.family()
						if family in announced:
							announced[family].pop(change.index(),None)

		if rr_announced:
			for afi,safi in rr_announced:
				self._enhanced_refresh_start.remove((afi,safi))
				yield Update(RouteRefresh(afi,safi,RouteRefresh.end),Attributes())

			for change in self._enhanced_refresh_delay:
				self.insert_announced(change,True)
			self.enhanced_refresh_delay = []

			for update in self.updates(grouped):
				yield update
