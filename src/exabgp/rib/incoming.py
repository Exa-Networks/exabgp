"""store.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from exabgp.rib.cache import Cache

if TYPE_CHECKING:
    from exabgp.protocol.family import AFI, SAFI


class IncomingRIB(Cache):
    def __init__(self, cache: bool, families: set[tuple[AFI, SAFI]]) -> None:
        Cache.__init__(self, cache, families)

    # back to square one, all the routes are removed
    def clear(self) -> None:
        self.clear_cache()

    def reset(self) -> None:
        pass
