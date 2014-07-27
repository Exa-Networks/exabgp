# encoding: utf-8
"""
flag.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""


# =================================================================== Flag

class Flag (int):
	EXTENDED_LENGTH = 0x10  # .  16 - 0001 0000
	PARTIAL         = 0x20  # .  32 - 0010 0000
	TRANSITIVE      = 0x40  # .  64 - 0100 0000
	OPTIONAL        = 0x80  # . 128 - 1000 0000

	__slots__ = []

	def __str__ (self):
		r = []
		v = int(self)
		if v & 0x10:
			r.append("EXTENDED_LENGTH")
			v -= 0x10
		if v & 0x20:
			r.append("PARTIAL")
			v -= 0x20
		if v & 0x40:
			r.append("TRANSITIVE")
			v -= 0x40
		if v & 0x80:
			r.append("OPTIONAL")
			v -= 0x80
		if v:
			r.append("UNKNOWN %s" % hex(v))
		return " ".join(r)

	def matches (self,value):
		return self | 0x10 == value | 0x10
