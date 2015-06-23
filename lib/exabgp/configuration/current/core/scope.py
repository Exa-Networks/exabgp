# encoding: utf-8
"""
scope.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

# from copy import deepcopy


class Scope (object):
	def __init__ (self,error):
		self.error = error
		self._location = []
		self._added = set()
		self._all = {
			'template': {}
		}
		self._current = self._all

	def clear (self):
		self._location = []
		self._added = set()
		self._all = {
			'template': {}
		}
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

	def to_context (self,name=''):
		self._current = self._all
		for context in self._location:
			if context not in self._current:
				self._current[context] = {}
			self._current = self._current[context]
		if name:
			self._current = self._current.setdefault(name,{})

	def pop_context (self,name):
		returned = self._all.pop(name)

		def transfer (source,destination):
			for key,value in source.iteritems():
				if key not in destination:
					destination[key] = value
				elif isinstance(source[key], dict):
					transfer(source[key],destination[key])
				elif isinstance(source[key], list):
					destination.setdefault(key,[]).extend(value)
				else:
					raise RuntimeError('can not recursively copy this type of data')

		for inherit in returned.get('inherit',[]):
			if inherit not in self._all['template']:
				raise ValueError('invalid template name referenced')
			transfer(self._all['template'][inherit],returned)

		return returned

	# key / value

	def set (self, name, value):
		self._current[name] = value

	def attribute_add (self, name, data):
		self._current[name].attributes.add(data)
		if name not in self._added:
			self._added.add(name)

	def nlri_assign (self, name, command, data):
		self._current[name].nlri.assign(command,data)

	def nlri_add (self, name, command, data):
		self._current[name].nlri.add(command,data)

	def nlri_nexthop (self, name, data):
		self._current[name].nlri.nexthop = data

	def append (self, name, data):
		self._current.setdefault(name,[]).append(data)

	def extend (self, name, data):
		self._current.setdefault(name,[]).extend(data)

	def get (self, name='', default=None):
		if name:
			return self._current.get(name,default)
		return self._current

	def pop (self, name, default=None):
		return self._current.pop(name,default)
