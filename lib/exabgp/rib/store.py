# encoding: utf-8
"""
store.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message import IN
from exabgp.bgp.message import OUT
from exabgp.bgp.message import Update
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.update.attribute import Attributes

from exabgp.vendoring import six

# XXX: FIXME: we would not have to use so many setdefault if we pre-filled the dicts with the families


class Store (object):
	def __init__ (self, families):
		# XXX: FIXME: we can decide to not cache the routes we seen and let the backend do it for us and save the memory
		self._watchdog = {}
		self.cache = False
		self.families = families
		self.clear()

		# clear
		self._seen = {}
		self._new_nlri = {}
		self._new_attr_af_nlri = {}
		self._new_attribute = {}

		# clear + reset
		self._enhanced_refresh_start = []
		self._enhanced_refresh_delay = []

	# will resend all the routes once we reconnect
	def reset (self):
		# WARNING : this function can run while we are in the updates() loop too !
		self._enhanced_refresh_start = []
		self._enhanced_refresh_delay = []
		for _ in self.updates(True):
			pass

	# back to square one, all the routes are removed
	def clear (self):
		self._seen = {}
		self._new_nlri = {}
		self._new_attr_af_nlri = {}
		self._new_attribute = {}
		self.reset()

	def sent_changes (self, families=None):
		# families can be None or []
		requested_families = self.families if families is None else set(families).intersection(self.families)

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
						self.add_to_rib(change,True)
		else:
			for family in requested_families:
				for change in _announced(family):
					self.add_to_rib(change,True)

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
		for change in self._new_nlri.values():
			yield change

	def replace (self, previous, changes):
		for change in previous:
			change.nlri.action = OUT.WITHDRAW
			self.add_to_rib(change,True)

		for change in changes:
			self.add_to_rib(change,True)

	def add_to_rib_watchdog (self, change):
		watchdog = change.attributes.watchdog()
		withdraw = change.attributes.withdraw()
		if watchdog:
			if withdraw:
				self._watchdog.setdefault(watchdog,{}).setdefault('-',{})[change.index()] = change
				return True
			self._watchdog.setdefault(watchdog,{}).setdefault('+',{})[change.index()] = change
		self.add_to_rib(change)
		return True

	def announce_watchdog (self, watchdog):
		if watchdog in self._watchdog:
			for change in self._watchdog[watchdog].get('-',{}).values():
				change.nlri.action = OUT.ANNOUNCE  # pylint: disable=E1101
				self.add_to_rib(change)
				self._watchdog[watchdog].setdefault('+',{})[change.index()] = change
				self._watchdog[watchdog]['-'].pop(change.index())

	def withdraw_watchdog (self, watchdog):
		if watchdog in self._watchdog:
			for change in self._watchdog[watchdog].get('+',{}).values():
				change.nlri.action = OUT.WITHDRAW
				self.add_to_rib(change)
				self._watchdog[watchdog].setdefault('-',{})[change.index()] = change
				self._watchdog[watchdog]['+'].pop(change.index())

	def insert_received (self, change):
		if not self.cache:
			return
		elif change.nlri.action == IN.ANNOUNCED:
			self._seen.get(change.nlri.family(),{})[change.index()] = change
		else:
			self._seen.get(change.nlri.family(),{}).pop(change.index(),None)

	def add_to_rib (self, change, force=False):
		# WARNING: do not call change.nlri.index as it does not prepend the family
		# WARNING : this function can run while we are in the updates() loop

		# self._seen[family][nlri-index] = change

		# self._new_nlri[nlri-index] = change : we are modifying this nlri
		# this is useful to iterate and find nlri currently handled

		# self._new_attr_af_nlri[attr-index][family][nlri-index] = change : add or remove the nlri
		# this is the best way to iterate over NLRI when generating updates
		# sharing attributes, then family

		# self._new_attribute[attr-index] = attributes of one of the changes
		# makes our life easier, but could be removed

		# import traceback
		# traceback.print_stack()
		# print "inserting", change.extensive()

		if not force and self._enhanced_refresh_start:
			self._enhanced_refresh_delay.append(change)
			return

		change_nlri_index = change.index()
		change_family = change.nlri.family()
		change_attr_index = change.attributes.index()

		attr_af_nlri = self._new_attr_af_nlri
		new_nlri = self._new_nlri
		new_attr = self._new_attribute

		# removing a route before we had time to announce it ?
		if change_nlri_index in new_nlri:
			# pop removes the entry
			old_change = new_nlri.pop(change_nlri_index)
			old_attr_index = old_change.attributes.index()
			# do not delete new_attr, other routes may use it
			del attr_af_nlri[old_attr_index][change_family][change_nlri_index]
			# do not delete the rest of the dict tree as:
			#  we may have to recreate it otherwise
			#  it will be deleted once used anyway
			#  we have to check for empty data in the updates() loop (so why do it twice!)

			# if we cache sent NLRI and this NLRI was never sent before, we do not need to send a withdrawal
			# as the route removed before we could announce it
			if self.cache and old_change.nlri.action == OUT.ANNOUNCE and change.nlri.action == OUT.WITHDRAW:
				if change_nlri_index not in self._seen.get(change.nlri.family(),{}):
					return

		if self.cache and not force:
			if change.nlri.action == OUT.ANNOUNCE:
				seen = self._seen.get(change.nlri.family(),{})
				if change_nlri_index in seen:
					old_change = seen[change_nlri_index]
					# it is a duplicate route
					if old_change.attributes.index() == change.attributes.index() and old_change.nlri.nexthop.index() == change.nlri.nexthop.index():
						return

		# add the route to the list to be announced
		attr_af_nlri.setdefault(change_attr_index,{}).setdefault(change_family,{})[change_nlri_index] = change
		new_nlri[change_nlri_index] = change

		if change_attr_index not in new_attr:
			new_attr[change_attr_index] = change.attributes

	def updates (self, grouped):
		def _update (seen,change):
			if not self.cache:
				return
			family = change.nlri.family()
			index = change.index()
			if change.nlri.action == OUT.ANNOUNCE:
				seen.setdefault(family,{})[index] = change
			else:
				if family not in seen:
					return
				seen[family].pop(index,None)

		rr_announced = []

		for afi,safi in self._enhanced_refresh_start:
			rr_announced.append((afi,safi))
			yield Update(RouteRefresh(afi,safi,RouteRefresh.start),Attributes())

		attr_af_nlri = self._new_attr_af_nlri
		new_attr = self._new_attribute

		for attr_index,per_family in attr_af_nlri.items():
			for family, changes in per_family.items():
				if not changes:
					continue

				# only yield once we have a consistent state, otherwise it will go wrong
				# as we will try to modify things we are iterating over and using

				seen = self._seen
				attributes = new_attr[attr_index]

				if grouped:
					for change in changes.values():
						yield Update(change.nlri, attributes)
						_update(seen,change)
				else:
					for change in changes.values():
						for nlri in change.nlri:
							yield Update([nlri,], attributes)
						_update(seen,change)

		self._new_nlri = {}
		self._new_attr_af_nlri = {}
		self._new_attribute = {}

		if rr_announced:
			for afi,safi in rr_announced:
				self._enhanced_refresh_start.remove((afi,safi))
				yield Update(RouteRefresh(afi,safi,RouteRefresh.end),Attributes())

			for change in self._enhanced_refresh_delay:
				self.add_to_rib(change,True)
			self._enhanced_refresh_delay = []

			for update in self.updates(grouped):
				yield update
