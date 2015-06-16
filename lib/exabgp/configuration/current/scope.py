# encoding: utf-8
"""
scope.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from copy import deepcopy



class Scope (object):
	def __init__ (self,error):
		self.error = error
		self._location = []
		self._added = set()
		self._all = {}
		self._current = self._all

	def clear (self):
		self._location = []
		self._added = set()
		self._all = {}
		self._current = self._all

	# context

	def enter (self,location):
		self._location.append(location)

	def leave (self):
		if not len(self._location):
			return ''  # This is signaling an issue to the caller without raising
		return self._location.pop()

	def location (self):
		return '/'.join(self._location)

	# context

	def to_context (self):
		self._current = self._all
		for context in self._location:
			if context not in self._current:
				self._current[context] = {}
			self._current = self._current[context]

	def pop_context (self,name):
		returned = self._all.pop(name)

		# support old style group
		group = self._all.get('group',{})
		for key,content in group.iteritems():
			if key not in returned:
				# it was a deep copy
				returned[key] = content
			elif key in self._added:
				returned.setdefault(key,[]).extend(group[key])

		return returned

	# key / value

	def set (self, name, value):
		self._current[name] = value

	def add (self, name, data):
		# XXX: Can raise Notify when adding attributes, as Change.add can raise
		self._current[name].add(data)
		if name not in self._added:
			self._added.add(name)

	# add a new prefix
	def append (self, name, data):
		self._current.setdefault(name,[]).append(data)

	# add a new prefix
	def last (self, name):
		return self._current[name]

	def pop_last (self,name):
		return self._current.pop(name)
