# encoding: utf-8
"""
action.py

Created by Thomas Mangin on 2022-05-19.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# =================================================================== Direction
#

from enum import IntEnum


class Action(IntEnum):
    UNSET = 0x00
    ANNOUNCE = 0x01
    WITHDRAW = 0x02
