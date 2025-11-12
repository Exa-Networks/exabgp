"""routerid.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations
from typing import Type

from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IPv4

# ===================================================================== RouterID
#


class RouterID(IPv4):
    def __init__(self, ip: str, packed: bytes | None = None) -> None:
        if IPv4.toafi(ip) != AFI.ipv4:
            raise ValueError('wrong address family')
        IPv4.__init__(self, ip, packed)

    @classmethod
    def unpack(cls: Type[RouterID], data: bytes) -> RouterID:  # pylint: disable=W0221
        return cls('.'.join(str(_) for _ in data), data)
