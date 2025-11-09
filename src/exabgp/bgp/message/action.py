
"""
action.py

Created by Thomas Mangin on 2022-05-19.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# =================================================================== Direction
#

from __future__ import annotations

from enum import IntEnum


class Action(IntEnum):
    UNSET = 0x00
    ANNOUNCE = 0x01
    WITHDRAW = 0x02

    def __str__(self):
        return self.__format__('s')

    def __format__(self, what):
        if what == 's':
            if self is Action.ANNOUNCE:
                return 'announce'
            if self is Action.WITHDRAW:
                return 'withdraw'
            if self is Action.UNSET:
                return 'unset'
        return 'invalid'
