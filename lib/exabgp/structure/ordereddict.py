# encoding: utf-8
'''
ordereddict.py

Created by Thomas Mangin on 2013-03-18.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
'''

class OrderedDict (dict):
	def __init__(self, args):
		dict.__init__(self, args)
		self._order = [_ for _,__ in args]

	def __setitem__(self, key, value):
		dict.__setitem__(self, key, value)
		if key in self._order:
			self._order.remove(key)
		self._order.append(key)

	def __delitem__(self, key):
		dict.__delitem__(self, key)
		self._order.remove(key)

	def order(self):
		return self._order[:]

	def ordered_items(self):
		return [(key,self[key]) for key in self._order]

	def keys(self):
		return self.order()
