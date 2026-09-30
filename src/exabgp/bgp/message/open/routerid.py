"""routerid.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.util.types import Buffer
from typing import Type

from exabgp.protocol.ip import IPFactory, IPv4

# ===================================================================== RouterID
#


class RouterID(IPv4):
    def __init__(self, ip: str) -> None:
        IPv4.__init__(self, IPv4.pton(ip))

    @classmethod
    def from_string(cls, string: str, klass: IPFactory | None = None) -> RouterID:
        """Build a RouterID rather than the registered IPv4 address class."""
        # Like ClusterID, this factory always returns its own identifier type.
        return cls(string)

    @classmethod
    def unpack_routerid(cls: Type[RouterID], data: Buffer) -> RouterID:
        return cls(IPv4.ntop(data))
