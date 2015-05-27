# encoding: utf-8
"""
resource.py

Created by Thomas Mangin on 2015-05-15.
Copyright (c) 2015-2015 Exa Networks. All rights reserved.
"""

from exabgp.util import string_is_hex


class Resource (int):
	NAME = ''
	codes = {}
	names = {}

	def __str__ (self):
		return self.names.get(self,'unknown %s type %d' % (self.NAME,int(self)))

	@classmethod
	def named (cls,string):
		name = string.lower().replace('_','-')
		if name in cls.codes:
			return cls(cls.codes[name])
		if string.isdigit():
			value = int(string)
			if value in cls.names:
				return cls(value)
		if string_is_hex(string):
			value = int(string[2:],16)
			if value in cls.names:
				return cls(value)
		raise ValueError('unknown %s %s' % (cls.NAME,name))
