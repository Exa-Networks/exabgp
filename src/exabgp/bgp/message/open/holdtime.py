"""holdtime.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack

# =================================================================== HoldTime


class HoldTime(int):
    MAX = 0xFFFF
    MIN = 3  # RFC 4271 Section 4.2 - minimum hold time in seconds (or 0 to disable keepalives)
    KEEPALIVE_DIVISOR = 3  # RFC 4271 Section 4.4 - keepalive interval = hold time / 3

    def pack(self):
        return pack('!H', self)

    def keepalive(self):
        return int(self / self.KEEPALIVE_DIVISOR)

    def __len__(self):
        return 2
