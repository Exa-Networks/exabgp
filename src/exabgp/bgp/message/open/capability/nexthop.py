"""nexthop.py

Created by Thomas Mangin on 2019-05-23.
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
from exabgp.bgp.message.notification import Notify
from exabgp.logger import log, lazymsg

# ================================================================ NextHop
#


@Capability.register()
class NextHop(Capability, list[tuple[AFI, SAFI, AFI]]):
    ID: ClassVar[int] = Capability.CODE.NEXTHOP

    def __init__(self, data: tuple[tuple[AFI, SAFI, AFI], ...] = ()) -> None:
        super().__init__()
        for afi, safi, nhafi in data:
            self.add_nexthop(afi, safi, nhafi)

    def add_nexthop(self, afi: AFI, safi: SAFI, nhafi: AFI) -> None:
        if (afi, safi, nhafi) not in self:
            self.append((afi, safi, nhafi))

    def __str__(self) -> str:
        families = ','.join([f'{afi!s} {safi!s} {nhafi!s}' for (afi, safi, nhafi) in self])
        return f'NextHop({families})'

    def json(self) -> str:
        conversions = ','.join(
            [f' "{afi!s}/{safi!s}/{nhafi!s}"' for (afi, safi, nhafi) in self],
        )
        return f'{{ "name": "nexthop", "conversion": [{conversions} ] }}'

    def extract_capability_bytes(self) -> list[bytes]:
        rs = b''
        for afi, safi, nhafi in self:
            rs += afi.pack_afi() + pack('!B', 0) + safi.pack_safi() + nhafi.pack_afi()
        return [
            rs,
        ]

    @classmethod
    def unpack_capability(cls, instance: Capability, data: bytes, capability: CapabilityCode) -> Capability:  # pylint: disable=W0613
        assert isinstance(instance, NextHop)
        # Check if this capability was already received (instance would have entries)
        if len(instance) > 0:
            log.debug(lazymsg('capability.nexthop.duplicate action=merge'), 'parser')
        # Each NextHop entry is 6 bytes: AFI(2) + reserved(1) + SAFI(1) + NextHop AFI(2)
        while data:
            if len(data) < 6:
                raise Notify(2, 0, f'NextHop capability truncated: need 6 bytes per entry, got {len(data)}')
            afi = AFI.unpack_afi(data[:2])
            safi = SAFI.unpack_safi(data[3:4])
            nexthop = AFI.unpack_afi(data[4:6])
            if (afi, safi, nexthop) in instance:

                def _log_dup(afi: AFI = afi, safi: SAFI = safi, nexthop: AFI = nexthop) -> str:
                    return f'duplicate AFI/SAFI/NextHop in capability: {afi}/{safi}/{nexthop}'

                log.debug(_log_dup, 'parser')
            else:
                instance.add_nexthop(afi, safi, nexthop)
            data = data[6:]
        return instance
