# encoding: utf-8
"""
fragment.py

Created by Thomas Mangin on 2010-02-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.enum import Enum
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

class Fragment (Enum):
	NOT      = 0x00
	DONT     = 0x01
	IS       = 0x02
	FIRST    = 0x04
	LAST     = 0x08
	# reserved = 0xF0


Fragment.UNKNOWN = 'unknown fragment value %s'

Fragment.VALUE = {
	'not-a-fragment':   Fragment(Fragment.NOT),
	'dont-fragment':  Fragment(Fragment.DONT),
	'is-fragment':    Fragment(Fragment.IS),
	'first-fragment': Fragment(Fragment.FIRST),
	'last-fragment':  Fragment(Fragment.LAST),
}

Fragment.NAME = {
	Fragment(Fragment.NOT):   'not-a-fragment',
	Fragment(Fragment.DONT):  'dont-fragment',
	Fragment(Fragment.IS):    'is-fragment',
	Fragment(Fragment.FIRST): 'first-fragment',
	Fragment(Fragment.LAST):  'last-fragment',
}
