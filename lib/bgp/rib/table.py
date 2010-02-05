#!/usr/bin/env python
# encoding: utf-8
"""
table.py

Created by Thomas Mangin on 2009-08-26.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import time

# - : remove the route
# + : add a new route
# * : update an existing route (as we use str() and that a route includes the prefix and attributes, may not be used often)

class Table (object):

	def __init__ (self,supervisor):
		self._plus = {}
		self._minus = {}
		self.supervisor = supervisor

	# This interface is very good for the file change but not if you want to update from network
	def recalculate (self):
		routes = self.supervisor.neighbor.routes
		for route in routes:
			self._add(route)
		for prefix in self._plus.keys():
			route = self._plus[prefix][1]
			if route not in routes:
				self._remove(route)
		return self

	def _add (self,route):
		prefix = str(route)
		if prefix in self._plus.keys():
			if route != self._plus[prefix][1]:
				self._plus[prefix] = (time.time(),route,'*')
			return
		self._plus[prefix] = (time.time(),route,'+')

	def _remove (self,route):
		prefix = str(route)
		if prefix in self._plus.keys():
			self._minus[prefix] = (time.time(),self._plus[prefix][1])
			del self._plus[prefix]

	def changed (self,when):
		"""table.changed must _always_ returns routes to remove before routes to add and must _always_ finish by the time"""
		for prefix in self._minus.keys():
			t,r = self._minus[prefix]
			if when < t:
				yield ('-',r)
		for prefix in self._plus.keys():
			t,r,o = self._plus[prefix]
			if when < t:
				yield (o,r)
		yield ('',time.time())

	def purge (self,when):
		for prefix in self._plus.keys():
			t,p = self._plus[prefix]
			if t < when:
				del self._plus[prefix]
		for prefix in self._minus.keys():
			t = self._minus[prefix]
			if t < when:
				del self._minus[prefix]


