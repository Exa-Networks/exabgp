# encoding: utf-8
"""
direction.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# =================================================================== Direction
#


class OUT(object):
    UNSET = 0x00
    ANNOUNCE = 0x01
    WITHDRAW = 0x02


class IN(object):
    UNSET = 0x00
    ANNOUNCED = 0x01
    WITHDRAWN = 0x02
