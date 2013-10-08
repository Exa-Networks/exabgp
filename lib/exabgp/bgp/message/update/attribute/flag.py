# encoding: utf-8
"""
flag.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

# =================================================================== Flag

class Flag (int):
	EXTENDED_LENGTH = 0x10  # .  16
	PARTIAL         = 0x20  # .  32
	TRANSITIVE      = 0x40  # .  64
	OPTIONAL        = 0x80  # . 128

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
