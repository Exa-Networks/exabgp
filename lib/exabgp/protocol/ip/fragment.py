# encoding: utf-8
"""
fragment.py

Created by Thomas Mangin on 2010-02-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""


# =================================================================== Fragment

# Uses bitmask operand format defined above.
#   0   1   2   3   4   5   6   7
# +---+---+---+---+---+---+---+---+
# |   Reserved    |LF |FF |IsF|DF |
# +---+---+---+---+---+---+---+---+
#
# Bitmask values:
# +  Bit 7 - Don't fragment (DF)
# +  Bit 6 - Is a fragment (IsF)
# +  Bit 5 - First fragment (FF)
# +  Bit 4 - Last fragment (LF)

class Fragment (int):
	NOT      = 0x00
	DONT     = 0x01
	IS       = 0x02
	FIRST    = 0x04
	LAST     = 0x08
	# reserved = 0xF0

	def __str__ (self):
		if self == self.NOT:
			return 'not-a-fragment'
		if self == self.DONT:
			return 'dont-fragment'
		if self == self.IS:
			return 'is-fragment'
		if self == self.FIRST:
			return 'first-fragment'
		if self == self.LAST:
			return 'last-fragment'
		return 'unknown fragment value %d' % int(self)


def NamedFragment (name):
	fragment = name.lower()
	if fragment == 'not-a-fragment':
		return Fragment(Fragment.NOT)
	if fragment == 'dont-fragment':
		return Fragment(Fragment.DONT)
	if fragment == 'is-fragment':
		return Fragment(Fragment.IS)
	if fragment == 'first-fragment':
		return Fragment(Fragment.FIRST)
	if fragment == 'last-fragment':
		return Fragment(Fragment.LAST)
	raise ValueError('unknown fragment name %s' % fragment)
