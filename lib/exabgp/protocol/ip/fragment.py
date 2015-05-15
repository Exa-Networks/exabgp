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

	_value = {
		'not-a-fragment': NOT,
		'dont-fragment':  DONT,
		'is-fragment':    IS,
		'first-fragment': FIRST,
		'last-fragment':  LAST,
	}

	_str = dict([(r,l) for (l,r) in _value.items()])

	def __str__ (self):
		return self._str.get(self,'unknown fragment value %d' % int(self))

	@staticmethod
	def named (fragment):
		name = fragment.lower().replace('_','-')
		if name in Fragment._value:
			return Fragment(Fragment._value[name])
		raise ValueError('unknown fragment name %s' % fragment)
