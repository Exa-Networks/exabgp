# encoding: utf-8
"""
enum.py

Created by Thomas Mangin on 2010-02-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""


class Enum (int):
	VALUE = {}
	NAME = {}
	UNKNOWN = {}

	@classmethod
	def Name (klass,name):
		lower = name.lower()

		if lower in klass.VALUE:
			return klass.VALUE[lower]

		if lower.isdigit():
			code = klass(lower)
			if code in klass.NAME:
				return klass.VALUE[klass.NAME[code]]

		raise ValueError(klass.UNKNOWN % lower)

	def __str__ (self):
		return self.NAME.get(self,self.UNKNOWN % ('%d' % self))
