# encoding: utf-8
"""
fragment.py

Created by Thomas Mangin on 2010-02-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.protocol.resource import BitResource


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


class Fragment(BitResource):
    NAME = 'fragment'

    NOT = 0x00
    DONT = 0x01
    IS = 0x02
    FIRST = 0x04
    LAST = 0x08
    # reserved = 0xF0

    codes = dict(
        (k.lower().replace('_', '-'), v)
        for (k, v) in {
            'NOT-A-FRAGMENT': NOT,
            'DONT-FRAGMENT': DONT,
            'IS-FRAGMENT': IS,
            'FIRST-FRAGMENT': FIRST,
            'LAST-FRAGMENT': LAST,
        }.items()
    )

    names = dict([(r, l) for (l, r) in codes.items()])
