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
		self.content = []
		self.location = []
		self._added = set()

	def clear (self):
		self.content = [{}]
		self.location = ['root']

	# set a value
	def set (self, name, value):
		self.content[-1][name] = value

	def new_context (self):
		self.content.append({})

	def pop_context (self):
		returned = self.content.pop(-1)

		if len(self.content):
			for key,content in self.content[-1].iteritems():
				if key not in returned:
					# it was a deep copy
					returned[key] = content
				elif key in self._added:
					returned.setdefault(key,[]).extend(self.content[-2][key])

		return returned

	def add (self, name, data):
		# XXX: Can raise Notify when adding attributes
		self.content[-1][name][-1].add(data)
		if name not in self._added:
			self._added.add(name)

	# add a new prefix
	def append (self, name, data):
		self.content[-1].setdefault(name,[]).append(data)

	# add a new prefix
	def last (self, name):
		return self.content[-1][name][-1]

	def enter (self,location):
		self.location.append(location)

	def leave (self):
		if not len(self.location):
			return ''
		return self.location.pop()
