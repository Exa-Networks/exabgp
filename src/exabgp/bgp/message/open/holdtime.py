"""holdtime.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar

from exabgp.util.intvalue import IntValue

from struct import pack

# =================================================================== HoldTime


class HoldTime(IntValue):
    MAX: ClassVar[int] = 0xFFFF
    MIN: ClassVar[int] = 3  # RFC 4271 Section 4.2 - minimum hold time in seconds (or 0 to disable keepalives)
    KEEPALIVE_DIVISOR: ClassVar[int] = 3  # RFC 4271 Section 4.4 - keepalive interval = hold time / 3

    def pack_holdtime(self) -> bytes:
        return pack('!H', self.value)

    def keepalive(self) -> int:
        return int(self.value / self.KEEPALIVE_DIVISOR)

    def __len__(self) -> int:
        return 2
