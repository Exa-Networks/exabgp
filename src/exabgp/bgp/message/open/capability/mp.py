"""mp.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from typing import ClassVar, List, Optional

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import _AFI
from exabgp.protocol.family import _SAFI
from exabgp.bgp.message.open.capability.capability import Capability

# ================================================================ MultiProtocol
#


@Capability.register()
class MultiProtocol(Capability, list):  # type: ignore[type-arg]
    ID: ClassVar[int] = Capability.CODE.MULTIPROTOCOL

    def __str__(self) -> str:
        families = ','.join([f'{afi!s} {safi!s}' for (afi, safi) in self])
        return f'Multiprotocol({families})'

    def json(self) -> str:
        families = ','.join([f' "{afi!s}/{safi!s}"' for (afi, safi) in self])
        return f'{{ "name": "multiprotocol", "families": [{families} ] }}'

    def extract(self) -> List[bytes]:
        rs: List[bytes] = []
        for v in self:
            rs.append(pack('!H', v[0]) + pack('!H', v[1]))
        return rs

    @staticmethod
    def unpack_capability(instance: MultiProtocol, data: bytes, capability: Optional[int] = None) -> MultiProtocol:  # pylint: disable=W0613
        # XXX: FIXME: we should raise if we have twice the same AFI/SAFI
        afi: _AFI = AFI.unpack(data[:2])
        safi: _SAFI = SAFI.unpack(data[3])
        instance.append((afi, safi))
        return instance
