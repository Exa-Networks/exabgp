#!/usr/bin/env python
# encoding: utf-8
"""
table.py

Created by Thomas Mangin on 2009-08-26.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import time
from threading import Lock

class Table (object):
	lock = Lock()
	
	def __init__ (self):
		self._plus = {}
		self._minus = {}

	# This interface is very good for the file change but not if you want to update from network
	def update (self,routes):
		with self.lock:
			for route in routes:
				self._add(route)
			for raw in self._plus.keys():
				route = self._plus[raw][1]
				if route not in routes:
					self._remove(route)
			return self
	
	def _add (self,route):
		raw = route.raw
		if raw in self._plus.keys():
			if route == self._plus[raw]:
				return
		self._plus[raw] = (time.time(),route)
	
	def _remove (self,route):
		raw = route.raw
		if raw in self._plus.keys():
			self._minus[raw] = (time.time(),self._plus[raw][1])
			del self._plus[raw]

	def changed (self,when):
		"""table.changed must _always_ returns routes to remove before routes to add and must _always_ finish by the time"""
		with self.lock:
			for raw in self._minus.keys():
				t,r = self._minus[raw]
				if when < t:
					yield ('-',r)
			for raw in self._plus.keys():
				t,r = self._plus[raw]
				if when < t:
					yield ('+',r)
			yield ('',time.time())
	
	def purge (self,when):
		with self.lock:
			for raw in self._plus.keys():
				t,p = self._plus[raw]
				if t < when:
					del self._plus[k]
			for raw in self._minus.keys():
				t = self._minus[raw]
				if t < when:
					del self._minus[raw]
				
		
