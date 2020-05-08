# encoding: utf-8
"""
version.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.util import character

# =================================================================== Version
#


class Version(int):
    def pack(self):
        return character(self)
