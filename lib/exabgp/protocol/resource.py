# encoding: utf-8
"""
resource.py

Created by Thomas Mangin on 2015-05-15.
Copyright (c) 2015-2015 Exa Networks. All rights reserved.
"""


class Resource (int):
	_NAME = ''
	_VALUE = {}
	_STRING = {}

	def __str__ (self):
		return self._STRING.get(self,'unknown icmp type %d' % int(self))

	@classmethod
	def named (cls,string):
		name = string.lower().replace('_','-')
		if name in cls._VALUE:
			return cls(cls._VALUE[name])
		raise ValueError('unknown %s %s' % (cls._NAME,name))
