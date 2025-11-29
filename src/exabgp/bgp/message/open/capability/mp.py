"""mp.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from typing import ClassVar

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.logger import log

# ================================================================ MultiProtocol
#


@Capability.register()
class MultiProtocol(Capability, list):
    ID: ClassVar[int] = Capability.CODE.MULTIPROTOCOL

    def __str__(self) -> str:
        families = ','.join([f'{afi!s} {safi!s}' for (afi, safi) in self])
        return f'Multiprotocol({families})'

    def json(self) -> str:
        families = ','.join([f' "{afi!s}/{safi!s}"' for (afi, safi) in self])
        return f'{{ "name": "multiprotocol", "families": [{families} ] }}'

    def extract(self) -> list[bytes]:
        rs: list[bytes] = []
        for v in self:
            rs.append(pack('!H', v[0]) + pack('!H', v[1]))
        return rs

    @staticmethod
    def unpack_capability(
        instance: MultiProtocol, data: bytes, capability: CapabilityCode | None = None
    ) -> MultiProtocol:  # pylint: disable=W0613
        afi: AFI = AFI.unpack_afi(data[:2])
        safi: SAFI = SAFI.unpack_safi(data[3:4])
        if (afi, safi) in instance:

            def _log_dup(afi: AFI = afi, safi: SAFI = safi) -> str:
                return f'duplicate AFI/SAFI in MultiProtocol capability: {afi}/{safi}'

            log.debug(_log_dup, 'parser')
        else:
            instance.append((afi, safi))
        return instance
