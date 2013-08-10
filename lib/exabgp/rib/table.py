# encoding: utf-8
"""
table.py

Created by Thomas Mangin on 2009-08-26.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import time

# - : remove the route
# + : add a new route
# * : update an existing route (as we use str() and that a route includes the prefix and attributes, may not be used often)

# This is our Adj-RIBs-Out
class Table (object):

	def __init__ (self,peer):
		self.peer = peer
		self.reset()

	def reset (self):
		self._plus = {}
		self._minus = {}

	# This interface is very good for the file change but not if you want to update from network
	def recalculate (self):
		changes = self.peer.neighbor.store.dump()

		# remove ...
		for index in self._plus.keys():
			if index not in changes:
				self._minus[index] = (time.time(),self._plus[index][1])
				del self._plus[index]

		# add ....
		for index,changed in changes.iteritems():
			if index in self._plus:
				if changed != self._plus[index][1]:
					self._plus[index] = (time.time(),changed,'*')
			else:
				self._plus[index] = (time.time(),changed,'+')

		return self

	def changed (self,when):
		"""table.changed must _always_ returns routes to remove before routes to add and must _always_ finish by the time"""
		for index in self._minus:
			t,r = self._minus[index]
			if when < t:
				yield ('-',r)
		# XXX: FIXME: delete the entry in _minus ??
		for index in self._plus.keys():
			t,r,o = self._plus[index]
			if when < t:
				yield (o,r)
		yield ('',time.time())

	def purge (self,when):
		for index in self._plus.keys():
			t,p = self._plus[index]
			if t < when:
				del self._plus[index]
		for index in self._minus.keys():
			t = self._minus[index]
			if t < when:
				del self._minus[index]
